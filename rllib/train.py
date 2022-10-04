#!/usr/bin/env python
import json
import os
from pathlib import Path
import yaml
import typer

import ray
from ray.tune.resources import resources_to_json, json_to_resources
from ray.tune.tune import run_experiments
from ray.tune.schedulers import create_scheduler
from ray.rllib.utils.framework import try_import_tf, try_import_torch
from ray.rllib.common import CLIArguments as cli
from ray.rllib.common import FrameworkEnum


def import_backends():
    """Try to import both backends for flag checking/warnings."""
    tf1, tf, tfv = try_import_tf()
    torch, _ = try_import_torch()


# Create the "train" Typer app
train_app = typer.Typer()


def _patch_path(path: str):
    """
    Patch a path to be relative to the current working directory.

    Args:
        path: relative input path.

    Returns: Patched path.
    """
    # This script runs in the ray/rllib dir.
    rllib_dir = Path(__file__).parent
    if isinstance(path, list):
        return [_patch_path(i) for i in path]
    elif isinstance(path, dict):
        return {_patch_path(k): _patch_path(v) for k, v in path.items()}
    elif isinstance(path, str):
        if os.path.exists(path):
            return path
        else:
            abs_path = str(rllib_dir.absolute().joinpath(path))
            return abs_path if os.path.exists(abs_path) else path
    else:
        return path


def load_experiments_from_file(config_file: str):
    with open(config_file) as f:
        experiments = yaml.safe_load(f)
    return experiments


@train_app.command()
def file(
    # File-based arguments.
    config_file: str = cli.ConfigFile,
    # Additional config arguments used for overriding.
    v: bool = cli.V,
    vv: bool = cli.VV,
    framework: FrameworkEnum = cli.Framework,
    trace: bool = cli.Trace,
    # Ray cluster options.
    local_mode: bool = cli.LocalMode,
    ray_address: str = cli.RayAddress,
    ray_ui: bool = cli.RayUi,
    ray_num_cpus: int = cli.RayNumCpus,
    ray_num_gpus: int = cli.RayNumGpus,
    ray_num_nodes: int = cli.RayNumNodes,
    ray_object_store_memory: int = cli.RayObjectStoreMemory,
    # Ray scheduling options.
    resume: bool = cli.Resume,
    scheduler: str = cli.Scheduler,
    scheduler_config: str = cli.SchedulerConfig,
):
    """Train a reinforcement learning agent from file.
    The file argument is required to run this command.

    Grid search example via RLlib CLI:\n
      rllib train file tuned_examples/ppo/cartpole-ppo.yaml\n\n

    Grid search example via executable:\n
      ./train.py file tuned_examples/ppo/cartpole-ppo.yaml\n\n
    """

    import_backends()

    framework = framework.value if framework else None

    experiments = load_experiments_from_file(config_file)

    return run_rllib_experiments(
        experiments=experiments,
        v=v,
        vv=vv,
        framework=framework,
        trace=trace,
        ray_num_nodes=ray_num_nodes,
        ray_num_cpus=ray_num_cpus,
        ray_num_gpus=ray_num_gpus,
        ray_object_store_memory=ray_object_store_memory,
        ray_ui=ray_ui,
        ray_address=ray_address,
        local_mode=local_mode,
        resume=resume,
        scheduler=scheduler,
        scheduler_config=scheduler_config,
    )


@train_app.callback(invoke_without_command=True)
def run(
    # Context object for subcommands
    ctx: typer.Context,
    # Config-based arguments.
    run: str = cli.Run,
    env: str = cli.Env,
    config: str = cli.Config,
    stop: str = cli.Stop,
    experiment_name: str = cli.ExperimentName,
    num_samples: int = cli.NumSamples,
    checkpoint_freq: int = cli.CheckpointFreq,
    checkpoint_at_end: bool = cli.CheckpointAtEnd,
    local_dir: str = cli.LocalDir,
    restore: str = cli.Restore,
    resources_per_trial: str = cli.ResourcesPerTrial,
    keep_checkpoints_num: int = cli.KeepCheckpointsNum,
    checkpoint_score_attr: str = cli.CheckpointScoreAttr,
    upload_dir: str = cli.UploadDir,
    # Additional config arguments used for overriding.
    v: bool = cli.V,
    vv: bool = cli.VV,
    framework: FrameworkEnum = cli.Framework,
    trace: bool = cli.Trace,
    # Ray cluster options.
    local_mode: bool = cli.LocalMode,
    ray_address: str = cli.RayAddress,
    ray_ui: bool = cli.RayUi,
    ray_num_cpus: int = cli.RayNumCpus,
    ray_num_gpus: int = cli.RayNumGpus,
    ray_num_nodes: int = cli.RayNumNodes,
    ray_object_store_memory: int = cli.RayObjectStoreMemory,
    # Ray scheduling options.
    resume: bool = cli.Resume,
    scheduler: str = cli.Scheduler,
    scheduler_config: str = cli.SchedulerConfig,
):
    """Train a reinforcement learning agent from command line options.
    The options --env and --algo/--run are required to run this command.

    Training example via RLlib CLI:\n
        rllib train --run DQN --env CartPole-v1\n\n
    """

    # If no subcommand is specified, simply run the following lines as the
    # "rllib train" main command.
    if ctx.invoked_subcommand is None:

        # we only check for backends when actually running the command. otherwise the
        # start-up time is too slow.
        import_backends()

        framework = framework.value if framework else None

        config = json.loads(config)
        resources_per_trial = json_to_resources(resources_per_trial)

        # Load a single experiment from configuration
        experiments = {
            experiment_name: {  # i.e. log to ~/ray_results/default
                "run": run,
                "checkpoint_freq": checkpoint_freq,
                "checkpoint_at_end": checkpoint_at_end,
                "keep_checkpoints_num": keep_checkpoints_num,
                "checkpoint_score_attr": checkpoint_score_attr,
                "local_dir": local_dir,
                "resources_per_trial": (
                    resources_per_trial and resources_to_json(resources_per_trial)
                ),
                "stop": json.loads(stop),
                "config": dict(config, env=env),
                "restore": restore,
                "num_samples": num_samples,
                "sync_config": {
                    "upload_dir": upload_dir,
                },
            }
        }

        return run_rllib_experiments(
            experiments=experiments,
            v=v,
            vv=vv,
            framework=framework,
            trace=trace,
            ray_num_nodes=ray_num_nodes,
            ray_num_cpus=ray_num_cpus,
            ray_num_gpus=ray_num_gpus,
            ray_object_store_memory=ray_object_store_memory,
            ray_ui=ray_ui,
            ray_address=ray_address,
            local_mode=local_mode,
            resume=resume,
            scheduler=scheduler,
            scheduler_config=scheduler_config,
        )


def run_rllib_experiments(
    experiments,
    v: cli.V,
    vv: cli.VV,
    framework: str,
    trace: cli.Trace,
    ray_num_nodes: cli.RayNumNodes,
    ray_num_cpus: cli.RayNumCpus,
    ray_num_gpus: cli.RayNumGpus,
    ray_object_store_memory: cli.RayObjectStoreMemory,
    ray_ui: cli.RayUi,
    ray_address: cli.RayAddress,
    local_mode: cli.LocalMode,
    resume: cli.Resume,
    scheduler: cli.Scheduler,
    scheduler_config: cli.SchedulerConfig,
):

    # Override experiment data with command line arguments.
    verbose = 1
    for exp in experiments.values():
        # Bazel makes it hard to find files specified in `args` (and `data`).
        # Look for them here.
        # NOTE: Some of our yaml files don't have a `config` section.
        input_ = exp.get("config", {}).get("input")
        if input_ and input_ != "sampler":
            exp["config"]["input"] = _patch_path(input_)

        if not exp.get("env") and not exp.get("config", {}).get("env"):
            raise ValueError(
                "You either need to provide an --env argument or pass"
                "an `env` key with a valid environment to your `config`"
                "argument."
            )
        elif framework is not None:
            exp["config"]["framework"] = framework
        if trace:
            if exp["config"]["framework"] not in ["tf2", "tfe"]:
                raise ValueError("Must enable --eager to enable tracing.")
            exp["config"]["eager_tracing"] = True
        if v:
            exp["config"]["log_level"] = "INFO"
            verbose = 3  # Print details on trial result
        if vv:
            exp["config"]["log_level"] = "DEBUG"
            verbose = 3  # Print details on trial result

    # Initialize the Ray cluster with the specified options.
    if ray_num_nodes:
        # Import this only here so that train.py also works with
        # older versions (and user doesn't use `--ray-num-nodes`).
        from ray.cluster_utils import Cluster

        cluster = Cluster()
        for _ in range(ray_num_nodes):
            cluster.add_node(
                num_cpus=ray_num_cpus or 1,
                num_gpus=ray_num_gpus or 0,
                object_store_memory=ray_object_store_memory,
            )
        ray.init(address=cluster.address)
    else:
        ray.init(
            include_dashboard=ray_ui,
            address=ray_address,
            object_store_memory=ray_object_store_memory,
            num_cpus=ray_num_cpus,
            num_gpus=ray_num_gpus,
            local_mode=local_mode,
        )

    # Run the Tune experiment and return the trials.
    scheduler_config = json.loads(scheduler_config)
    trials = run_experiments(
        experiments,
        scheduler=create_scheduler(scheduler, **scheduler_config),
        resume=resume,
        verbose=verbose,
        concurrent=True,
    )
    ray.shutdown()
    return trials


def main():
    """Run the CLI."""
    train_app()


if __name__ == "__main__":
    main()
