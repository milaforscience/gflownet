#!/bin/bash
# Installs a virtual environment with cuda torch
#
# Arguments
# $1: Environment name
# 
### Load modules (Python and CUDA) ###
module --force purge
module load python/3.10
module load cuda/11.8
#
### Make and activate environment ###
if [ ! -d "$1" ]; then
    python -m virtualenv $1
    
fi
source $1/bin/activate 
#
### Core packages ###
# Update pip
python -m pip install --upgrade pip
# Force install six and appdirs to avoid issues
pip install --ignore-installed six appdirs
# Install PyTorch
# See: https://pytorch.org/
python -m pip install torch==2.0.1 --index-url https://download.pytorch.org/whl/cu118
# Requirements to run
# scikit-learn version to load correct RF proxy
python -m pip install numpy pandas scikit-learn==1.2.2 hydra-core tqdm torchtyping matplotlib
#
### Conditional requirements ###
# wandb: for logging onto WandB
python -m pip install wandb
### Dev packages ###
python -m pip install black flake8 isort pylint ipdb jupyter pytest pytest-repeat
