import pandas as pd
import numpy as np
from tqdm import tqdm
from pymatgen.core import Structure
from mp_api.client.mprester import MPRester
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
import matplotlib.pyplot as plt
import seaborn as sns
import os


class BaseMetric:
    def __init__(self) -> None:
        self.__name__ = self.__class__.__name__

    def compute(self, structures: Structure, **kwargs) -> dict:
        """Performs the computational part of a metric and returns a JSONable dictionnary

        Parameters
        ----------
        structures : Structure
        compositions : Composition

        Returns
        -------
        dict
            jsonable dictionary
        """
        return {}

    def plot(self, data_results: dict[str]):
        """Create various plots and prints given data_results dict. The data_result dic has as
        keys different datasets names and as values a dictionnary providing from the above
        compute function. You can typically print things or save plots to out_dir.

        Parameters
        ----------
        data_results :  dict[str]
            keys different datasets names and as values a dictionnary providing from the above
        compute function.

        Returns
        -------
        None
        """
        return None


class NumberOfElements(BaseMetric):
    def compute(self, structures: Structure, **kwargs) -> dict:
        n_elems = [len(s.composition.as_dict()) for s in structures]
        n_elems_distr = pd.Series(n_elems).value_counts().to_dict()
        return n_elems_distr

    def plot(self, data_results: dict[str]):
        for dataset_name, data in data_results.items():
            print(f"Dataset {dataset_name}")
            for n, amount in data.items():
                print(f"Number of {n}-elements materials:{amount}")
            print("")

        df = pd.DataFrame()
        for label, data in data_results.items():
            temp_df = pd.DataFrame(
                {
                    "Elements": list(data.keys()),
                    "Occurrences": list(data.values()),
                    "Dataset": label,
                }
            )
            df = pd.concat([df, temp_df], ignore_index=True)

        # Create the plot using Seaborn
        fig, ax = plt.subplots()
        sns.barplot(x="Elements", y="Occurrences", hue="Dataset", data=df, ax=ax)

        # Labeling the plot
        ax.set_xlabel("Elements")
        ax.set_ylabel("Occurrences")
        ax.set_title("Comparison of Element Occurrences")
        fig.savefig("number_of_elements.pdf")


class Rediscovery(BaseMetric):
    def __init__(self, rediscovery_path=None):
        super().__init__()
        if rediscovery_path is not None:
            self.ref = pd.read_csv(rediscovery_path)
        else:
            try:
                key = os.environ.get("MATPROJ_API_KEY")
                if key is None:
                    print(
                        "No MP Key. Set your env variable MATPROJ_API_KEY or remove the Rediscovery metric."
                    )
                    exit()
                self.ref = MPRester(key)
            except (KeyError, ValueError):
                print(
                    "No reference (either dataset or Materials Project API Key) present."
                )
                exit()

    def compute(self, structures):
        compositions = [s.composition.as_dict() for s in structures]
        matches = self._comp_rediscovery(compositions, self.ref)
        return {"matches": matches}

    def plot(self, data_results, out_dir):
        for data_name, results in data_results.items():
            print(f"Following matches were found for {data_name}")
            print(results)
            print(results["matches"])

    def _check_ref(self, query, ref):
        print(ref)
        if isinstance(ref, pd.DataFrame):
            ref = ref[ref.columns[8:-2]]
            for col in ref.columns:
                if col not in query:
                    query[col] = 0
            query_df = pd.Series(query)
            found = ref.loc[ref.eq(query_df).all(axis=1)]
            if len(found) > 0:
                return query, found.to_dict("index")
        elif isinstance(ref, MPRester):
            query_crit = [k for k, v in query.items() if v > 0]
            comp = "-".join(query_crit)
            docs = ref.get_structures(comp)
            for doc in docs:
                # for the entries returned, get the conventional structure
                # unreduced composition dictionary
                struc = doc
                SGA = SpacegroupAnalyzer(struc)
                struc = SGA.get_conventional_standard_structure()

                doc_comp = dict(struc.composition.get_el_amt_dict())
                if comp == doc_comp:
                    return query, doc_comp
        else:
            raise TypeError("Query cannot be made against reference")

        return (None, None)

    def _comp_rediscovery(self, compositions, reference):
        match_dix = {}
        for i, c in enumerate(tqdm(compositions)):
            comp_dic = c
            k, v = self._check_ref(comp_dic, reference)
            if v:
                match_dix[k] = v
        return match_dix