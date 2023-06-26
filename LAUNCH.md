# 🤝 Gflownet Launch tool help

## 💻 Command-line help

```sh
usage: launch.py [-h] [--help-md] [--job_name JOB_NAME] [--outdir OUTDIR]
                 [--cpus_per_task CPUS_PER_TASK] [--mem MEM] [--gres GRES]
                 [--partition PARTITION] [--modules MODULES]
                 [--conda_env CONDA_ENV] [--venv VENV] [--code_dir CODE_DIR]
                 [--jobs JOBS] [--dev] [--verbose] [--force]

optional arguments:
  -h, --help            show this help message and exit
  --help-md             Show an extended help message as markdown. Can be
                        useful to overwrite LAUNCH.md with `$ python launch.py
                        --help-md > LAUNCH.md`
  --job_name JOB_NAME   slurm job name to show in squeue. Defaults to crystal-
                        gfn
  --outdir OUTDIR       where to write the slurm .out file. Defaults to
                        $SCRATCH/crystals/logs/slurm
  --cpus_per_task CPUS_PER_TASK
                        number of cpus per SLURM task. Defaults to 2
  --mem MEM             memory per node (e.g. 32G). Defaults to 32G
  --gres GRES           gres per node (e.g. gpu:1). Defaults to gpu:1
  --partition PARTITION
                        slurm partition to use for the job. Defaults to long
  --modules MODULES     string after 'module load'. Defaults to anaconda/3
                        cuda/11.3
  --conda_env CONDA_ENV
                        conda environment name. Defaults to gflownet
  --venv VENV           path to venv (without bin/activate). Defaults to None
  --code_dir CODE_DIR   cd before running main.py (defaults to here). Defaults
                        to ~/ocp-project/gflownet
  --jobs JOBS           run file name in external/jobs (without .yaml).
                        Defaults to None
  --dev                 Don't run just, show what it would have run. Defaults
                        to False
  --verbose             print templated sbatch after running it. Defaults to
                        False
  --force               skip user confirmation. Defaults to False

```

## 🎛️ Default values

```yaml
code_dir      : ~/ocp-project/gflownet
conda_env     : gflownet
cpus_per_task : 2
dev           : False
force         : False
gres          : gpu:1
job_name      : crystal-gfn
jobs          : None
main_args     : None
mem           : 32G
modules       : anaconda/3 cuda/11.3
outdir        : $SCRATCH/crystals/logs/slurm
partition     : long
template      : /Users/victor/Documents/Github/gflownet-dev/sbatch/template-conda.sh
venv          : None
verbose       : False
```

## 🥳 User guide

In a word, use `launch.py` to fill in an sbatch template and submit either
a single job from the command-line, or a list of jobs from a `yaml` file.

Examples:

```sh
# using default job configuration, with script args from the command-line:
$ python launch.py user=$USER logger.do.online=False

# overriding the default job configuration and adding script args:
$ python launch.py --template=sbatch/template-venv.sh \
    --venv='~/.venvs/gfn' \
    --modules='python/3.7 cuda/11.3' \
    user=$USER logger.do.online=False

# using a yaml file to specify multiple jobs to run:
$ python launch.py --jobs=jobs/comp-sg-lp/v0" --mem=32G
```

### 🤓 How it works

1. All experiment files should be in `external/jobs`
    1. Note that all the content in `external/` is **ignored by git**
2. You can nest experiment files infinitely, let's say you work on crystals and call your experiment `explore-losses.yaml` then you could put your config in `external/jobs/crystals/explore-losses.yaml`
3. An experiment file contains 2 main sections:
    1. `shared:` contains the configuration that will be, you guessed it, shared across jobs.
    2. `jobs:` lists configurations for the SLURM jobs that you want to run. The `shared` configuration will be loaded first, then updated from the `run`'s.
4. Both `shared` and `job` dicts contain (optional) sub-sections:
    1. `slurm:` contains what's necessary to parameterize the SLURM job
    2. `script:` contains a dict version of the command-line args to give `main.py`

    ```yaml
    script:
      gflownet:
        optimizer:
          lr: 0.001

    # is equivalent to
    script:
      gflownet.optimizer.lr: 0.001

    # and will be translated to
    python main.py gflownet.optimizer.lr=0.001
    ```

5. Launch the SLURM jobs with `python launch.py --jobs=crystals/explore-losses`
    1. `launch.py` knows to look in `external/jobs/` and add `.yaml`
    2. You can overwrite anything from the command-line: the command-line arguments have the final say and will overwrite all the jobs' final dicts. Run `python launch.py -h` to see all the known args.
    3. You can also override `script` params from the command-line: unknown arguments will be given as-is to `main.py`. For instance `python launch.py --jobs=crystals/explore-losses --mem=32G env.some_param=value` is valid
6. `launch.py` loads a template (`sbatch/template-conda.sh`) by default, and fills it with the arguments specified, then writes the filled template in `external/launched_sbatch_scripts/crystals/` with the current datetime and experiment file name.
7. `launch.py` executes `sbatch` in a subprocess to execute the filled template above
8. A summary yaml is also created there, with the exact experiment file and appended `SLURM_JOB_ID`s returned by `sbatch`

### 📝 Case-study

Let's study the following example:

```sh
python launch.py --jobs=crystals/explore-losses --mem=64G
```

Say the file `./external/jobs/crystals/explore-losses.yaml` contains:

```yaml
# Contents of external/jobs/crystals/explore-losses.yaml

# Shared section across jobs
shared:
  # job params
  slurm:
      template: sbatch/template-conda.sh # which template to use
      modules: anaconda/3 cuda/11.3      # string of the modules to load
      conda_env: gflownet                # name of the environment
      code_dir: ~/ocp-project/gflownet   # where to find the repo
      gres: gpu:1                        # slurm gres
      mem: 16G                           # node memory
      cpus_per_task: 2                   # task cpus

  # main.py params
  script:
    user: $USER
    +experiments: neurips23/crystal-comp-sg-lp.yaml
    gflownet:
      __value__: flowmatch               # special entry if you want to see `gflownet=flowmatch`
    optimizer:
      lr: 0.0001                     # will be translated to `gflownet.optimizer.lr=0.0001`

# list of slurm jobs to execute
jobs:
  - {}                                   # empty dictionary = just run with the shared params
  - slurm:                               # change this job's slurm params
      partition: unkillable
    script:                              # change this job's script params
      gflownet:
        policy:
          backward: null
  - script:
      gflownet:
        __value__: trajectorybalance
```

Then the launch command-line ^ will execute 3 jobs with the following configurations:

```bash
python main.py user=$USER +experiments=neurips23/crystal-comp-sg-lp.yaml gflownet=flowmatch gflownet.optimizer.lr=0.0001

python main.py user=$USER +experiments=neurips23/crystal-comp-sg-lp.yaml gflownet=flowmatch gflownet.optimizer.lr=0.0001 gflownet.policy.backward=None

python main.py user=$USER +experiments=neurips23/crystal-comp-sg-lp.yaml gflownet=trajectorybalance gflownet.optimizer.lr=0.0001
```

And their SLURM configuration will be similar as the `shared.slurm` params, with the following differences:

1. The second job will have `partition: unkillable` instead of the default (`long`).
2. They will all have `64G` of memory instead of the default (`32G`) because the `--mem=64G` command-line
    argument overrides everything.