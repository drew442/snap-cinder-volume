# SPDX-FileCopyrightText: 2026 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import Mock

from cinder_volume import cinder_volume, context


def _base_config() -> dict:
    """Create a minimal valid snap config payload."""
    return {
        "settings": {"debug": False},
        "database": {"url": "mysql+pymysql://cinder:pw@10.0.0.10/cinder"},
        "rabbitmq": {"url": "rabbit://cinder:pw@10.0.0.11:5672/openstack"},
        "cinder": {"project-id": "proj-id", "user-id": "user-id"},
    }


class TestGenericCinderVolumeLVMSAN:
    """Test lvm-san backend compatibility in GenericCinderVolume."""

    def test_backend_contexts_discovers_lvm_san_backend(self):
        """Test dynamic discovery loads lvm-san backend contexts."""
        config_payload = _base_config()
        config_payload["lvm-san"] = {
            "lvm-san-a": {
                "volume-backend-name": "lvm-san.backend-a",
                "volume-group": "cinder-volumes",
                "iscsi-ip-address": "10.20.30.40",
                "target-helper": "lioadm",
                "target-protocol": "iscsi",
                "lvm-type": "thin",
                "lvm-pool-name": "cinder-thin",
            }
        }

        mock_snap = Mock()
        mock_snap.config.get_options.return_value.as_dict.return_value = config_payload

        service = cinder_volume.GenericCinderVolume()
        backend_contexts = service.backend_contexts(mock_snap)

        assert "lvm-san-a" in backend_contexts.contexts
        lvm_ctx = backend_contexts.contexts["lvm-san-a"]
        assert isinstance(lvm_ctx, context.LvmSanBackendContext)
        assert lvm_ctx.cinder_context()["volume_driver"] == (
            "cinder.volume.drivers.lvm.LVMVolumeDriver"
        )
        assert lvm_ctx.cinder_context()["volume_group"] == "cinder-volumes"
        assert lvm_ctx.cinder_context()["iscsi_ip_address"] == "10.20.30.40"
