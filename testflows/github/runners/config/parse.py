import yaml
import logging
import logging.config

from ..providers.hetzner import config as _hetzner_config
from ..providers.aws import config as _aws_config
from ..providers.scaleway import config as _scaleway_config
from ..providers.dedicated_static import config as _ds_config

from .config import (
    Config,
    standby_runner,
    cloud,
    deploy_,
    path,
    provider_list,
    coerce_deploy_field,
)

logger = logging.getLogger("testflows.github.runners")

# Flat cloud keys -> cloud.deploy field (`type` -> `server_type`).
_CLOUD_DEPLOY_FIELDS = {
    "type": "server_type",
    "server_type": "server_type",
    "image": "image",
    "location": "location",
    "setup_script": "setup_script",
}


def parse_config(filename: str):
    """Load and parse yaml configuration file into config object.

    Does not check if ssh_key, or additional_ssh_keys exist.
    Does not check server_type exists.
    Does not check image exists.
    Does not check location exists.
    Does not check server_type is available for the location.
    Does not check if image exists for the server_type.
    """
    with open(filename, "r") as f:
        doc = yaml.load(f, Loader=yaml.SafeLoader)

    if doc.get("config") is None:
        assert False, "config: entry is missing"

    doc = doc["config"]

    if doc.get("setup_script"):
        assert (
            False
        ), "config.setup_script is deprecated, use the new config.scripts option"

    if doc.get("startup_x64_script"):
        assert (
            False
        ), "config.startup_x64_script is deprecated, use the new config.scripts option"

    if doc.get("startup_arm64_script"):
        assert (
            False
        ), "config.startup_x64_script is deprecated, see the new config.scripts option"

    if doc.get("ssh_key") is not None:
        assert isinstance(doc["ssh_key"], str), "config.ssh_key: is not a string"
        doc["ssh_key"] = path(doc["ssh_key"], check_exists=False)

    if doc.get("additional_ssh_keys") is not None:
        assert isinstance(
            doc["additional_ssh_keys"], list
        ), "config.additional_ssh_keys: not a list"
        for i, key in enumerate(doc["additional_ssh_keys"]):
            assert isinstance(
                key, str
            ), f"config.additional_ssh_keys[{i}]: is not a string"

    if doc.get("with_label") is not None:
        assert isinstance(doc["with_label"], list), "config.with_label: is not a list"
        for i, label in enumerate(doc["with_label"]):
            assert isinstance(label, str), f"config.with_label[{i}]: is not a string"
        doc["with_label"] = [label.lower().strip() for label in doc["with_label"]]

    if doc.get("label_prefix") is not None:
        assert isinstance(
            doc["label_prefix"], str
        ), "config.label_prefix: is not a string"
        doc["label_prefix"] = doc["label_prefix"].lower().strip()

    if doc.get("meta_label") is not None:
        assert isinstance(
            doc["meta_label"], dict
        ), "config.meta_label is not a dictionary"
        for i, meta in enumerate(doc["meta_label"]):
            assert isinstance(
                meta, str
            ), f"config.meta_label.{meta}: name is not a string"
            assert isinstance(
                doc["meta_label"][meta], list
            ), f"config.meta_label.{meta}: is not a list"
            for j, v in enumerate(doc["meta_label"][meta]):
                assert isinstance(
                    v, str
                ), f"config.meta_label.{meta}[{j}]: is not a string"
            # Preserve declaration order (deduped): scale_up consumes it as the
            # cross-provider fallback priority, so a set would randomize it.
            doc["meta_label"][meta] = list(dict.fromkeys(doc["meta_label"][meta]))

        doc["meta_label"] = {
            meta.lower().strip(): [
                label.lower().strip() for label in doc["meta_label"][meta]
            ]
            for meta in doc["meta_label"]
        }

    if doc.get("recycle") is not None:
        assert isinstance(doc["recycle"], bool), "config.recycle: is not a boolean"

    if "recycle_without_rebuild" in doc:
        assert False, (
            "config.recycle_without_rebuild has been removed; use "
            "config.providers.hetzner.recycle_with_rebuild instead "
            "(note the inverse semantics)"
        )

    if doc.get("recycle_grace_period") is not None:
        v = doc["recycle_grace_period"]
        assert isinstance(v, int), "config.recycle_grace_period: is not integer"
        assert v >= 0, "config.recycle_grace_period: must be >= 0"

    if doc.get("end_of_life") is not None:
        v = doc["end_of_life"]
        assert isinstance(v, int), "config.end_of_life: is not integer"
        assert v > 0 and v < 60, "config.end_of_life: is not > 0 and < 60"

    if doc.get("delete_random") is not None:
        assert isinstance(
            doc["delete_random"], bool
        ), "config.delete_random: is not a boolean"

    if doc.get("max_runners") is not None:
        v = doc["max_runners"]
        assert isinstance(v, int) and v > 0, "config.max_runners: is not an integer > 0"

    if doc.get("max_runners_for_label") is not None:
        assert isinstance(
            doc["max_runners_for_label"], list
        ), "config.max_runners_for_label: is not a list"
        for i, item in enumerate(doc["max_runners_for_label"]):
            assert isinstance(
                item, dict
            ), f"config.max_runners_for_label[{i}]: is not an object"
            assert (
                "labels" in item
            ), f"config.max_runners_for_label[{i}]: missing 'labels' field"
            assert (
                "max" in item
            ), f"config.max_runners_for_label[{i}]: missing 'max' field"
            assert isinstance(
                item["labels"], list
            ), f"config.max_runners_for_label[{i}].labels: is not a list"
            assert (
                isinstance(item["max"], int) and item["max"] > 0
            ), f"config.max_runners_for_label[{i}].max: is not an integer > 0"
            for j, label in enumerate(item["labels"]):
                assert isinstance(
                    label, str
                ), f"config.max_runners_for_label[{i}].labels[{j}]: is not a string"
                assert (
                    label.strip()
                ), f"config.max_runners_for_label[{i}].labels[{j}]: cannot be empty"
            # Convert to our internal format (set of labels, count)
            doc["max_runners_for_label"][i] = (
                set(label.strip().lower() for label in item["labels"]),
                item["max"],
            )

    if doc.get("max_runners_in_workflow_run") is not None:
        v = doc["max_runners_in_workflow_run"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_runners_in_workflow_run: is not an integer > 0"

    # Hetzner's default image/type/location/volume moved under
    # providers.hetzner.defaults (uniform with aws/scaleway); the top-level
    # keys are gone. Hard-error so an old config fails loudly instead of
    # silently ignoring them.
    for _removed in (
        "default_image",
        "default_server_type",
        "default_location",
        "default_volume_location",
        "default_volume_size",
    ):
        assert doc.get(_removed) is None, (
            f"config.{_removed}: is not supported; use "
            f"config.providers.hetzner.defaults instead"
        )

    if doc.get("workers") is not None:
        v = doc["workers"]
        assert isinstance(v, int) and v > 0, "config.workers: is not an integer > 0"

    if doc.get("scripts") is not None:
        try:
            doc["scripts"] = path(doc["scripts"])
        except Exception as e:
            assert False, f"config.scripts: {e}"

    if doc.get("max_powered_off_time") is not None:
        v = doc["max_powered_off_time"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_powered_off_time: is not an integer > 0"

    if doc.get("max_unused_runner_time") is not None:
        v = doc["max_unused_runner_time"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_unused_runner_time: is not an integer > 0"

    if doc.get("max_runner_registration_time") is not None:
        v = doc["max_runner_registration_time"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_runner_registration_time: is not an integer > 0"

    if doc.get("max_server_ready_time") is not None:
        v = doc["max_server_ready_time"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_server_ready_time: is not an integer > 0"

    if doc.get("scale_up_interval") is not None:
        v = doc["scale_up_interval"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.scale_up_interval: is not an integer > 0"

    if doc.get("scale_down_interval") is not None:
        v = doc["scale_down_interval"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.scale_down_interval: is not an integer > 0"

    if doc.get("metrics_port") is not None:
        v = doc["metrics_port"]
        assert (
            isinstance(v, int) and v > 0 and v < 65536
        ), "config.metrics_port: is not an integer between 1 and 65535"

    if doc.get("metrics_host") is not None:
        v = doc["metrics_host"]
        assert isinstance(v, str), "config.metrics_host: is not a string"
        assert v.strip(), "config.metrics_host: cannot be empty"

    if doc.get("dashboard_port") is not None:
        v = doc["dashboard_port"]
        assert (
            isinstance(v, int) and v > 0 and v < 65536
        ), "config.dashboard_port: is not an integer between 1 and 65535"

    if doc.get("dashboard_host") is not None:
        v = doc["dashboard_host"]
        assert isinstance(v, str), "config.dashboard_host: is not a string"
        assert v.strip(), "config.dashboard_host: cannot be empty"

    if doc.get("debug") is not None:
        assert isinstance(doc["debug"], bool), "config.debug: not a boolean"

    if doc.get("logger_config") is not None:
        assert (
            doc["logger_config"].get("loggers") is not None
        ), "config.logger_config.loggers is not defined"
        assert (
            doc["logger_config"]["loggers"].get("testflows.github.runners") is not None
        ), 'config.logger_config.loggers."testflows.github.runners" is not defined'
        assert (
            doc["logger_config"]["loggers"]["testflows.github.runners"].get("handlers")
            is not None
        ), 'config.logger_config.loggers."testflows.github.runners".handlers is not defined'

        assert isinstance(
            doc["logger_config"]["loggers"]["testflows.github.runners"]["handlers"],
            list,
        ), 'config.logger_config.loggers."testflows.github.runners".handlers is not a list'
        assert (
            "stdout" in doc["logger_config"]["loggers"]["testflows.github.runners"]["handlers"]
        ), 'config.logger_config.loggers."testflows.github.runners".handlers missing stdout'

        assert (
            doc["logger_config"]["handlers"].get("rotating_logfile") is not None
        ), "config.logger_config.handlers.rotating_logfile is not defined"
        assert (
            doc["logger_config"]["handlers"]["rotating_logfile"].get("filename")
            is not None
        ), "config.logger_config.handlers.rotating_logfile.filename is not defined"

        try:
            logging.config.dictConfig(doc["logger_config"])
        except Exception as e:
            assert False, f"config.logger_config: {e}"

    if doc.get("logger_format") is not None:
        _logger_format_columns = {}
        assert isinstance(
            doc["logger_format"], dict
        ), f"config.logger_format is not a dictionary"

        assert (
            doc["logger_format"].get("delimiter") is not None
        ), "config.logger_format.delimiter is not defined"
        assert isinstance(
            doc["logger_format"]["delimiter"], str
        ), f"config.logger_format.delimiter is not a string"

        assert (
            doc["logger_format"].get("columns") is not None
        ), "config.logger_format.columns  is not defined"
        assert isinstance(
            doc["logger_format"]["columns"], list
        ), "config.logger_format.columns is not a list"

        for i, item in enumerate(doc["logger_format"]["columns"]):
            assert (
                item.get("column") is not None
            ), f"config.logger_format[{i}].column is not defined"
            assert isinstance(
                item["column"], str
            ), f"config.logger_format[{i}].column is not a string"
            assert (
                item.get("index") is not None
            ), f"config.logger_format[{i}].index is not defined"
            assert (
                isinstance(item["index"], int) and item["index"] >= 0
            ), f"config.logger_format[{i}].index: {item['index']} is not an integer >= 0"
            assert (
                item.get("width") is not None
            ), f"config.logger_format[{i}].width is not defined"
            assert (
                isinstance(item["width"], int) and item["width"] >= 0
            ), f"config.logger_format[{i}].width: {item['width']} is not an integer >= 0"
            _logger_format_columns[item["column"]] = (item["index"], item["width"])
        doc["logger_format"]["columns"] = _logger_format_columns

        assert (
            doc["logger_format"].get("default") is not None
        ), "config.logger_format.default is not defined"
        assert isinstance(
            doc["logger_format"]["default"], list
        ), "config.logger_format.default is not an array"

        for i, item in enumerate(doc["logger_format"]["default"]):
            assert (
                item.get("column") is not None
            ), f"config.logger_format.default[{i}].column is not defined"
            assert (
                item["column"] in doc["logger_format"]["columns"]
            ), f"config.logger_format.default[{i}].column is not valid"
            if item.get("width") is not None:
                assert (
                    isinstance(item["width"], int) and item["width"] > 0
                ), f"config.logger_format.default[{i}].width is not an integer > 0"

    if doc.get("cloud") is not None:
        # Flat deploy keys are silently ignored; reject and show the fix.
        _cloud = doc["cloud"]
        _misplaced = [
            (key, field)
            for key, field in _CLOUD_DEPLOY_FIELDS.items()
            if _cloud.get(key) is not None
        ]
        if _misplaced:
            _moved = dict(_misplaced)
            _fixed = {k: v for k, v in _cloud.items() if k not in _moved}
            _fixed["deploy"] = dict(_cloud.get("deploy") or {})
            for _key, _field in _misplaced:
                _fixed["deploy"][_field] = _cloud[_key]
            _example = yaml.dump(
                {"cloud": _fixed}, default_flow_style=False, sort_keys=False
            ).rstrip()
            _names = ", ".join(f"cloud.{key}" for key, _ in _misplaced)
            assert False, (
                f"config.cloud: {_names} must be under cloud.deploy. "
                f"Corrected block:\n\n{_example}"
            )

        if doc["cloud"].get("server_name") is not None:
            assert isinstance(
                doc["cloud"]["server_name"], str
            ), "config.cloud.server_name: is not a string"

        if doc["cloud"].get("ssh_user") is not None:
            assert isinstance(
                doc["cloud"]["ssh_user"], str
            ), "config.cloud.ssh_user: is not a string"

        cloud_provider = doc["cloud"].get("provider") or "hetzner"
        assert cloud_provider in ("hetzner", "aws", "scaleway"), (
            "config.cloud.provider: must be one of 'hetzner', 'aws', 'scaleway' "
            f"(got {cloud_provider!r}); dedicated_static cannot host the controller"
        )

        raw_deploy = doc["cloud"].get("deploy") or {}
        if cloud_provider == "hetzner":
            # Hetzner deploy specs are hcloud-typed; coerce + keep the cx23/ubuntu
            # defaults from deploy_ when omitted.
            for field in ("server_type", "image", "location"):
                if raw_deploy.get(field) is not None:
                    try:
                        raw_deploy[field] = coerce_deploy_field(
                            cloud_provider, field, raw_deploy[field]
                        )
                    except ValueError as e:
                        assert False, f"config.cloud.deploy.{field}: {e}"
            if raw_deploy.get("setup_script") is not None:
                try:
                    raw_deploy["setup_script"] = path(raw_deploy["setup_script"])
                except Exception as e:
                    assert False, f"config.cloud.deploy.setup_script: {e}"
            deploy_obj = deploy_(**raw_deploy)
        else:
            # Non-Hetzner: keep specs as raw provider-native strings (validated at
            # deploy time via the provider's get_image/get_server_type/get_location);
            # do NOT inherit the Hetzner-shaped deploy_ defaults, so unset fields
            # fall back to the provider's own defaults in cloud.deploy.
            for field in ("server_type", "image", "location"):
                if raw_deploy.get(field) is not None:
                    assert isinstance(
                        raw_deploy[field], str
                    ), f"config.cloud.deploy.{field}: is not a string"
            deploy_kwargs = {
                "server_type": raw_deploy.get("server_type"),
                "image": raw_deploy.get("image"),
                "location": raw_deploy.get("location"),
            }
            if raw_deploy.get("setup_script") is not None:
                try:
                    deploy_kwargs["setup_script"] = path(raw_deploy["setup_script"])
                except Exception as e:
                    assert False, f"config.cloud.deploy.setup_script: {e}"
            deploy_obj = deploy_(**deploy_kwargs)

        doc["cloud"] = cloud(
            provider=cloud_provider,
            server_name=doc["cloud"].get("server_name") or cloud().server_name,
            host=doc["cloud"].get("host"),
            ssh_user=doc["cloud"].get("ssh_user"),
            deploy=deploy_obj,
        )

    if doc.get("standby_runners"):
        assert isinstance(
            doc["standby_runners"], list
        ), "config.standby_runners: is not a list"

        for i, entry in enumerate(doc["standby_runners"]):
            assert isinstance(
                entry, dict
            ), f"config.standby_runners[{i}]: is not an dictionary"
            if entry.get("labels") is not None:
                assert isinstance(
                    entry["labels"], list
                ), f"config.standby_runners[{i}].labels: is not a list"
                for j, label in enumerate(entry["labels"]):
                    assert isinstance(
                        label, str
                    ), f"config.standby_runners[{i}].labels[{j}]: {label} is not a string"
                entry["labels"] = [label.lower().strip() for label in entry["labels"]]
            if entry.get("count") is not None:
                v = entry["count"]
                assert (
                    isinstance(v, int) and v > 0
                ), f"config.standby_runners[{i}].count: is not an integer > 0"
            if entry.get("replenish_immediately") is not None:
                assert isinstance(
                    entry["replenish_immediately"], bool
                ), f"config.standby_runners[{i}].replenish_immediately: is not a boolean"

        doc["standby_runners"] = [
            standby_runner(**entry) for entry in doc["standby_runners"]
        ]

    if doc.get("server_prices") is not None:
        assert False, "config.server_prices: should not be defined"

    if doc.get("config_file") is not None:
        assert False, "config.config_file: should not be defined"

    if doc.get("service_mode") is not None:
        assert False, "config.service_mode: should not be defined"

    if doc.get("embedded_mode") is not None:
        assert False, "config.embedded_mode: should not be defined"

    if doc.get("hetzner_token") is not None:
        assert False, (
            "config.hetzner_token: is not supported; "
            "use config.providers.hetzner.token instead"
        )

    if doc.get("enabled_providers") is not None:
        assert False, (
            "config.enabled_providers: is not supported in the config file; "
            "use --provider on the command line instead"
        )

    if doc.get("provider") is not None:
        assert False, (
            "config.provider: is not supported in the config file; "
            "use --provider on the command line instead"
        )

    if doc.get("providers") is not None:
        _p = doc["providers"]
        assert isinstance(_p, dict), "config.providers: is not a dictionary"

        _hetzner = None
        if _p.get("hetzner") is not None:
            _hetzner = _hetzner_config.parse_config_section(_p["hetzner"])

        _aws = None
        if _p.get("aws") is not None:
            _aws = _aws_config.parse_config_section(_p["aws"])

        _scaleway = None
        if _p.get("scaleway") is not None:
            _scaleway = _scaleway_config.parse_config_section(_p["scaleway"])

        _dedicated_static = None
        if _p.get("dedicated_static") is not None:
            _dedicated_static = _ds_config.parse_config_section(
                _p["dedicated_static"],
                meta_label=doc.get("meta_label"),
                label_prefix=doc.get("label_prefix"),
            )

        _unimplemented = set(_p.keys()) - {
            "hetzner",
            "aws",
            "scaleway",
            "dedicated_static",
        }
        assert not _unimplemented, (
            f"config.providers: {', '.join(sorted(_unimplemented))} "
            f"{'is' if len(_unimplemented) == 1 else 'are'} not yet implemented"
        )

        doc["providers"] = provider_list(
            hetzner=_hetzner,
            aws=_aws,
            scaleway=_scaleway,
            dedicated_static=_dedicated_static,
        )

    try:
        return Config(**doc)
    except Exception as e:
        assert False, f"config: {e}"
