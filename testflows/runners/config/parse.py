import yaml

from .config import Config


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
            doc["meta_label"][meta] = set(doc["meta_label"][meta])

        doc["meta_label"] = {
            meta.lower().strip(): [
                label.lower().strip() for label in doc["meta_label"][meta]
            ]
            for meta in doc["meta_label"]
        }

    if doc.get("recycle") is not None:
        assert isinstance(doc["recycle"], bool), "config.recycle: is not a boolean"

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

    # Note: default_image, default_server_type, default_location, default_volume_*
    # are now handled by provider-specific configurations under providers.<name>.defaults.*

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
            doc["logger_config"]["loggers"].get("testflows.runners") is not None
        ), 'config.logger_config.loggers."testflows.runners" is not defined'
        assert (
            doc["logger_config"]["loggers"]["testflows.runners"].get("handlers")
            is not None
        ), 'config.logger_config.loggers."testflows.runners".handlers is not defined'

        assert isinstance(
            doc["logger_config"]["loggers"]["testflows.runners"]["handlers"],
            list,
        ), 'config.logger_config.loggers."testflows.runners".handlers is not a list'
        assert (
            "stdout" in doc["logger_config"]["loggers"]["testflows.runners"]["handlers"]
        ), 'config.logger_config.loggers."testflows.runners".handlers missing stdout'

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
        if doc["cloud"].get("server_name") is not None:
            assert isinstance(
                doc["cloud"]["server_name"], str
            ), "config.cloud.server_name: is not a string"
        if doc["cloud"].get("deploy") is not None:
            # Get provider for cloud deployment parsing
            provider_name = doc["cloud"].get("provider", "hetzner")

            # Import provider-specific functions for cloud deployment
            if provider_name == "hetzner":
                from ..providers.hetzner.args import (
                    image_type,
                    location_type,
                    server_type as provider_server_type,
                )
            elif provider_name in ["aws", "azure", "gcp", "scaleway"]:
                # For now, other providers don't support cloud deployment parsing
                # This will be implemented when those providers are fully supported
                pass
            else:
                raise ValueError(
                    f"Unknown provider '{provider_name}' for cloud deployment"
                )

            if (
                doc["cloud"]["deploy"].get("server_type") is not None
                and provider_name == "hetzner"
            ):
                try:
                    doc["cloud"]["deploy"]["server_type"] = provider_server_type(
                        doc["cloud"]["deploy"]["server_type"]
                    )
                except Exception as e:
                    assert False, f"config.cloud.deploy.server_type: {e}"
            if (
                doc["cloud"]["deploy"].get("image") is not None
                and provider_name == "hetzner"
            ):
                try:
                    doc["cloud"]["deploy"]["image"] = image_type(
                        doc["cloud"]["deploy"]["image"]
                    )
                except Exception as e:
                    assert False, f"config.cloud.deploy.image: {e}"
            if (
                doc["cloud"]["deploy"].get("location") is not None
                and provider_name == "hetzner"
            ):
                try:
                    doc["cloud"]["deploy"]["location"] = location_type(
                        doc["cloud"]["deploy"]["location"]
                    )
                except Exception as e:
                    assert False, f"config.cloud.deploy.location: {e}"
            if doc["cloud"]["deploy"].get("setup_script") is not None:
                try:
                    doc["cloud"]["deploy"]["setup_script"] = path(
                        doc["cloud"]["deploy"]["setup_script"]
                    )
                except Exception as e:
                    assert False, f"config.cloud.deploy.setup_script: {e}"

        if doc["cloud"].get("server_name"):
            doc["cloud"] = cloud(
                doc["cloud"]["server_name"],
                host=doc["cloud"].get("host"),
                deploy=deploy_(**doc["cloud"].get("deploy", {})),
            )
        else:
            doc["cloud"] = cloud(
                deploy=deploy_(**doc["cloud"].get("deploy", {})),
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

    try:
        return Config(**doc)
    except Exception as e:
        assert False, f"config: {e}"
