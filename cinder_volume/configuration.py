# SPDX-FileCopyrightText: 2024 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Configuration module for the cinder-volume snap.

This module holds the definition of all configuration options the snap
takes as input from `snap set`.
"""

import typing

import pydantic
import pydantic.alias_generators
from pydantic import Field


def to_kebab(value: str) -> str:
    """Convert a string to kebab-case."""
    return pydantic.alias_generators.to_snake(value).replace("_", "-")


class ParentConfig(pydantic.BaseModel):
    """Set common model configuration for all models."""

    model_config = pydantic.ConfigDict(
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=to_kebab,
        ),
    )


class DatabaseConfiguration(ParentConfig):
    """Configuration for database connection."""

    url: str


class RabbitMQConfiguration(ParentConfig):
    """Configuration for RabbitMQ connection."""

    url: str


class CinderConfiguration(ParentConfig):
    """Configuration for Cinder service."""

    project_id: str
    user_id: str
    image_volume_cache_enabled: bool = False
    image_volume_cache_max_size_gb: int = 0
    image_volume_cache_max_count: int = 0
    default_volume_type: str | None = None
    cluster: str | None = None


class Settings(ParentConfig):
    """General settings for the snap."""

    debug: bool = False
    enable_telemetry_notifications: bool = False


class BaseConfiguration(ParentConfig):
    """Base configuration class.

    This class should be the basis of downstream snaps.
    """

    settings: Settings = Settings()
    database: DatabaseConfiguration
    rabbitmq: RabbitMQConfiguration
    cinder: CinderConfiguration


class BaseBackendConfiguration(ParentConfig):
    """Base configuration for storage backends."""

    @pydantic.model_validator(mode="before")
    @classmethod
    def convert_extra_fields(cls, data):
        """Convert kebab-case keys to snake_case for extra fields."""
        if isinstance(data, dict):
            converted = {}
            defined_fields = set(cls.model_fields.keys())
            for key, value in data.items():
                snake_key = key.replace("-", "_")
                if snake_key in defined_fields:
                    # Defined field - keep original key for alias generator
                    converted[key] = value
                else:
                    # Extra field - convert to snake_case
                    converted[snake_key] = value
            return converted
        return data

    image_volume_cache_enabled: bool | None = None
    image_volume_cache_max_size_gb: int | None = None
    image_volume_cache_max_count: int | None = None
    volume_dd_blocksize: int | str = Field(default=4096, ge=512)
    volume_backend_name: str
    driver_ssl_cert: str | None = None


class CephConfiguration(BaseBackendConfiguration):
    """Configuration for Ceph storage backend."""

    rbd_exclusive_cinder_pool: bool = True
    report_discard_supported: bool = True
    rbd_flatten_volume_from_snapshot: bool = False
    auth: str = "cephx"
    mon_hosts: str
    rbd_pool: str
    rbd_user: str
    rbd_secret_uuid: str
    rbd_key: str


class LvmConfiguration(BaseBackendConfiguration):
    """All options recognised by the **LVM** Cinder driver."""

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Required
    volume_group: str

    # Core LVM driver settings
    lvm_type: str = Field(default="auto", pattern="^(default|thin|auto)$")
    lvm_mirrors: int = 0
    lvm_conf_file: str = "/etc/lvm/lvm.conf"
    lvm_suppress_fd_warnings: bool = False
    lvm_share_target: bool = False

    # Target / transport settings
    target_helper: str = Field(
        default="tgtadm",
        pattern="^(tgtadm|lioadm|scstadmin|iscsictl|fake)$",
    )
    target_protocol: str = Field(default="iscsi", pattern="^(iscsi|iser)$")
    target_ip_address: str = "$my_ip"
    target_port: int = 3260
    target_prefix: str = "iqn.2010-10.org.openstack:"
    target_secondary_ip_addresses: str | None = None

    # iSCSI settings (tgtadm)
    iscsi_iotype: str = Field(default="fileio", pattern="^(blockio|fileio|auto)$")
    iscsi_target_flags: str = ""
    iscsi_write_cache: str = Field(default="on", pattern="^(on|off)$")

    # SCST settings
    scst_target_driver: str = "iscsi"
    scst_target_iqn_name: str | None = None

    # Capacity and clearing
    volume_clear: str = Field(default="zero", pattern="^(none|zero)$")
    volume_clear_size: int = 0
    volume_clear_ionice: str | None = None
    volume_dd_blocksize: str = "1M"
    reserved_percentage: int = 0
    max_over_subscription_ratio: str = "20.0"
    volumes_dir: str = r"{{ snap_paths.common }}/lib/cinder/volumes"


class HitachiConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Hitachi VSP** Cinder driver.

    Defaults follow the upstream driver recommendations/documentation.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Mandatory connection parameters
    san_ip: pydantic.IPvAnyAddress
    san_username: str
    san_password: str
    hitachi_storage_id: str | int
    hitachi_pools: str  # comma‑separated list

    # Driver selection
    protocol: str = Field(default="fc", pattern="^(fc|iscsi)$")


class PureConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Pure Storage FlashArray** Cinder driver.

    This configuration supports iSCSI, Fibre Channel, and NVMe protocols
    with advanced features like replication, TriSync, and auto-eradication.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # FlashArray management IP/FQDN
    pure_api_token: str  # REST API authorization token
    protocol: str = Field(default="fc", pattern="^(iscsi|fc|nvme)$")


class DellSCConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Dell Storage Center** Cinder driver.

    This configuration supports iSCSI and Fibre Channel protocols
    with dual DSM support, network filtering, and comprehensive timeout controls.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # Dell DSM management IP/FQDN
    san_login: str  # DSM management username
    san_password: str  # DSM management password
    dell_sc_ssn: int  # Storage Center System Serial Number
    protocol: str = Field(default="fc", pattern="^(iscsi|fc)$")
    enable_unsupported_driver: typing.Literal[True]

    # Optional secondary DSM settings
    secondary_san_ip: pydantic.IPvAnyAddress | None = None
    secondary_san_login: str | None = None
    secondary_san_password: str | None = None


class DellpowerstoreConfiguration(BaseBackendConfiguration):
    """All options recognised by the **Dell PowerStore** Cinder driver.

    This configuration supports iSCSI, Fibre Channel and NVMe-TCP protocols.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",  # Allow extra fields not defined in the model
        alias_generator=pydantic.AliasGenerator(
            validation_alias=to_kebab,
            serialization_alias=pydantic.alias_generators.to_snake,
        ),
    )

    # Core required fields
    san_ip: pydantic.IPvAnyAddress  # Dell PowerStore management IP/FQDN
    san_login: str  # Dell PowerStore management username
    san_password: str  # Dell PowerStore management password
    protocol: str = Field(default="fc", pattern="^(iscsi|fc)$")


class Configuration(BaseConfiguration):
    """Holding additional configuration for the generic snap.

    This class is specific to this snap and should not be used in
    downstream snaps.
    """

    ceph: dict[str, CephConfiguration] = {}
    lvm: dict[str, LvmConfiguration] = {}
    hitachi: dict[str, HitachiConfiguration] = {}
    pure: dict[str, PureConfiguration] = {}
    dellsc: dict[str, DellSCConfiguration] = {}
    dellpowerstore: dict[str, DellpowerstoreConfiguration] = {}

    @pydantic.model_validator(mode="after")
    def validate_unique_backend_names(self):
        """Validate that all backend names are unique across all backend types."""
        backend_names = set()
        ceph_pools = set()

        # Check all backend types for unique backend names
        for backend_type, backends in [
            ("ceph", self.ceph),
            ("lvm", self.lvm),
            ("hitachi", self.hitachi),
            ("pure", self.pure),
            ("dellsc", self.dellsc),
            ("dellpowerstore", self.dellpowerstore),
        ]:
            for backend_key, backend in backends.items():
                # Check for duplicate backend names across all types
                if backend.volume_backend_name in backend_names:
                    raise ValueError(
                        f"Duplicate backend name '{backend.volume_backend_name}' "
                        f"found in {backend_type} backend '{backend_key}'"
                    )
                backend_names.add(backend.volume_backend_name)

                # Check for duplicate Ceph pools (only applies to Ceph backends)
                if backend_type == "ceph" and hasattr(backend, "rbd_pool"):
                    if backend.rbd_pool in ceph_pools:
                        raise ValueError(
                            f"Duplicate Ceph pool '{backend.rbd_pool}' "
                            f"found in backend '{backend_key}'"
                        )
                    ceph_pools.add(backend.rbd_pool)

        return self
