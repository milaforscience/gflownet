import torch
from gflownet.utils.molecule import torsions, constants

class DGLConformer:
    def __init__(self, atom_positions, smiles, torsion_indecies):
        self.graph = dgl_graph

    def apply_rotations(self, rotations):
        """
        Apply rotations (torsion angles updates)
        :param rotations: a sequence of torsion angle updates of length = number of bonds in the molecule.
        The order corresponds to the order of edges in self.graph, such that action[i] is
        an update for the torsion angle corresponding to the edge[2i]
        """
        self.graph = torsions.apply_rotations(self.graph, rotations)

    def randomise_torsion_angles(self):
        n_edges = self.graph.edges()[0].shape
        rotations = torch.rand(n_edges // 2) * 2 * torch.pi
        self.apply_rotations(rotations)
