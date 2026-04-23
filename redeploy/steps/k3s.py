"""k3s / Kubernetes domain steps."""
from __future__ import annotations

from ..models import ConflictSeverity, MigrationStep, StepAction


def _step(id: str, action: StepAction, description: str, **kw) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


FLUSH_K3S_IPTABLES = _step(
    id="flush_k3s_iptables",
    action=StepAction.SSH_CMD,
    description="Flush k3s CNI-HOSTPORT-DNAT + KUBE-* chains (stale rules block Docker-proxy on 80/443)",
    command=(
        "iptables -t nat -F CNI-HOSTPORT-DNAT 2>/dev/null || true && "
        "iptables -t nat -F CNI-HOSTPORT-MASQ 2>/dev/null || true && "
        "iptables -t nat -F KUBE-SERVICES 2>/dev/null || true && "
        "iptables -t nat -F KUBE-NODEPORTS 2>/dev/null || true && "
        "iptables -t filter -F KUBE-FORWARD 2>/dev/null || true && "
        "echo iptables-flushed"
    ),
    risk=ConflictSeverity.LOW,
)

DELETE_K3S_INGRESSES = _step(
    id="delete_k3s_ingresses",
    action=StepAction.KUBECTL_DELETE,
    description="Delete k3s ingresses to remove iptables DNAT rules",
    command="k3s kubectl delete ingress --all-namespaces --all 2>/dev/null || true",
    risk=ConflictSeverity.LOW,
)

STOP_K3S = _step(
    id="stop_k3s",
    action=StepAction.SYSTEMCTL_STOP,
    service="k3s",
    description="Stop k3s to free ports 80/443",
    command="systemctl stop k3s",
    risk=ConflictSeverity.MEDIUM,
    rollback_command="systemctl start k3s",
)

DISABLE_K3S = _step(
    id="disable_k3s",
    action=StepAction.SYSTEMCTL_DISABLE,
    service="k3s",
    description="Disable k3s on boot",
    command="systemctl disable k3s",
    risk=ConflictSeverity.LOW,
)

ALL: list[MigrationStep] = [
    FLUSH_K3S_IPTABLES,
    DELETE_K3S_INGRESSES,
    STOP_K3S,
    DISABLE_K3S,
]
