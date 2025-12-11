from enum import Enum
from .domain import Server, VM, VMPlacementPlan


class DemoData(Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


def generate_demo_data(demo: DemoData) -> VMPlacementPlan:
    """Generate demo data for the specified demo type."""
    if demo == DemoData.SMALL:
        return _generate_small()
    elif demo == DemoData.MEDIUM:
        return _generate_medium()
    elif demo == DemoData.LARGE:
        return _generate_large()
    else:
        raise ValueError(f"Unknown demo: {demo}")


def _generate_small() -> VMPlacementPlan:
    """
    Small demo: 5 servers, 20 VMs
    - 2 large servers (32 cores, 128GB, 1TB)
    - 3 medium servers (16 cores, 64GB, 512GB)
    - Mix of small, medium, and large VMs
    - Includes affinity and anti-affinity groups
    """
    servers = [
        # Large servers
        Server(id="s1", name="server-large-01", cpu_cores=32, memory_gb=128, storage_gb=1000, rack="rack-a"),
        Server(id="s2", name="server-large-02", cpu_cores=32, memory_gb=128, storage_gb=1000, rack="rack-b"),
        # Medium servers
        Server(id="s3", name="server-medium-01", cpu_cores=16, memory_gb=64, storage_gb=512, rack="rack-a"),
        Server(id="s4", name="server-medium-02", cpu_cores=16, memory_gb=64, storage_gb=512, rack="rack-b"),
        Server(id="s5", name="server-medium-03", cpu_cores=16, memory_gb=64, storage_gb=512, rack="rack-a"),
    ]

    vms = [
        # Web tier (affinity group - should be together)
        VM(id="vm1", name="web-01", cpu_cores=2, memory_gb=4, storage_gb=20, priority=3, affinity_group="web-tier"),
        VM(id="vm2", name="web-02", cpu_cores=2, memory_gb=4, storage_gb=20, priority=3, affinity_group="web-tier"),
        VM(id="vm3", name="web-03", cpu_cores=2, memory_gb=4, storage_gb=20, priority=3, affinity_group="web-tier"),

        # Database replicas (anti-affinity - must be on different servers)
        VM(id="vm4", name="db-primary", cpu_cores=8, memory_gb=32, storage_gb=200, priority=5, anti_affinity_group="db-cluster"),
        VM(id="vm5", name="db-replica-1", cpu_cores=8, memory_gb=32, storage_gb=200, priority=5, anti_affinity_group="db-cluster"),
        VM(id="vm6", name="db-replica-2", cpu_cores=8, memory_gb=32, storage_gb=200, priority=4, anti_affinity_group="db-cluster"),

        # API servers
        VM(id="vm7", name="api-01", cpu_cores=4, memory_gb=8, storage_gb=50, priority=4),
        VM(id="vm8", name="api-02", cpu_cores=4, memory_gb=8, storage_gb=50, priority=4),

        # Cache servers (affinity - benefit from being together)
        VM(id="vm9", name="cache-01", cpu_cores=4, memory_gb=16, storage_gb=30, priority=3, affinity_group="cache-tier"),
        VM(id="vm10", name="cache-02", cpu_cores=4, memory_gb=16, storage_gb=30, priority=3, affinity_group="cache-tier"),

        # Worker nodes
        VM(id="vm11", name="worker-01", cpu_cores=2, memory_gb=4, storage_gb=40, priority=2),
        VM(id="vm12", name="worker-02", cpu_cores=2, memory_gb=4, storage_gb=40, priority=2),
        VM(id="vm13", name="worker-03", cpu_cores=2, memory_gb=4, storage_gb=40, priority=2),
        VM(id="vm14", name="worker-04", cpu_cores=2, memory_gb=4, storage_gb=40, priority=2),

        # Monitoring
        VM(id="vm15", name="monitoring", cpu_cores=4, memory_gb=8, storage_gb=100, priority=3),
        VM(id="vm16", name="logging", cpu_cores=4, memory_gb=8, storage_gb=150, priority=3),

        # Dev/test VMs (lower priority)
        VM(id="vm17", name="dev-01", cpu_cores=2, memory_gb=4, storage_gb=30, priority=1),
        VM(id="vm18", name="dev-02", cpu_cores=2, memory_gb=4, storage_gb=30, priority=1),
        VM(id="vm19", name="test-01", cpu_cores=2, memory_gb=4, storage_gb=30, priority=1),
        VM(id="vm20", name="test-02", cpu_cores=2, memory_gb=4, storage_gb=30, priority=1),
    ]

    return VMPlacementPlan(name="SMALL", servers=servers, vms=vms)


def _generate_medium() -> VMPlacementPlan:
    """
    Medium demo: 10 servers, 50 VMs
    - Realistic small cluster scenario
    - Multiple affinity and anti-affinity groups
    """
    servers = [
        # Large servers (rack-a)
        Server(id="s1", name="server-large-01", cpu_cores=32, memory_gb=128, storage_gb=1000, rack="rack-a"),
        Server(id="s2", name="server-large-02", cpu_cores=32, memory_gb=128, storage_gb=1000, rack="rack-a"),
        Server(id="s3", name="server-large-03", cpu_cores=32, memory_gb=128, storage_gb=1000, rack="rack-b"),
        Server(id="s4", name="server-large-04", cpu_cores=32, memory_gb=128, storage_gb=1000, rack="rack-b"),
        # Medium servers
        Server(id="s5", name="server-medium-01", cpu_cores=16, memory_gb=64, storage_gb=512, rack="rack-a"),
        Server(id="s6", name="server-medium-02", cpu_cores=16, memory_gb=64, storage_gb=512, rack="rack-a"),
        Server(id="s7", name="server-medium-03", cpu_cores=16, memory_gb=64, storage_gb=512, rack="rack-b"),
        Server(id="s8", name="server-medium-04", cpu_cores=16, memory_gb=64, storage_gb=512, rack="rack-b"),
        # Small servers
        Server(id="s9", name="server-small-01", cpu_cores=8, memory_gb=32, storage_gb=256, rack="rack-a"),
        Server(id="s10", name="server-small-02", cpu_cores=8, memory_gb=32, storage_gb=256, rack="rack-b"),
    ]

    vms = []
    vm_id = 1

    # Web tier (6 VMs, affinity)
    for i in range(6):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"web-{i+1:02d}",
            cpu_cores=2, memory_gb=4, storage_gb=20,
            priority=3, affinity_group="web-tier"
        ))
        vm_id += 1

    # Database cluster (3 VMs, anti-affinity)
    for i, name in enumerate(["db-primary", "db-replica-1", "db-replica-2"]):
        vms.append(VM(
            id=f"vm{vm_id}", name=name,
            cpu_cores=8, memory_gb=32, storage_gb=200,
            priority=5, anti_affinity_group="db-cluster"
        ))
        vm_id += 1

    # API servers (8 VMs)
    for i in range(8):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"api-{i+1:02d}",
            cpu_cores=4, memory_gb=8, storage_gb=50,
            priority=4
        ))
        vm_id += 1

    # Cache tier (4 VMs, affinity)
    for i in range(4):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"cache-{i+1:02d}",
            cpu_cores=4, memory_gb=16, storage_gb=30,
            priority=3, affinity_group="cache-tier"
        ))
        vm_id += 1

    # Worker nodes (12 VMs)
    for i in range(12):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"worker-{i+1:02d}",
            cpu_cores=2, memory_gb=4, storage_gb=40,
            priority=2
        ))
        vm_id += 1

    # Analytics cluster (3 VMs, anti-affinity for HA)
    for i in range(3):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"analytics-{i+1:02d}",
            cpu_cores=8, memory_gb=24, storage_gb=150,
            priority=3, anti_affinity_group="analytics-cluster"
        ))
        vm_id += 1

    # Monitoring & logging (4 VMs)
    for name in ["prometheus", "grafana", "elasticsearch", "kibana"]:
        vms.append(VM(
            id=f"vm{vm_id}", name=name,
            cpu_cores=4, memory_gb=8, storage_gb=100,
            priority=3
        ))
        vm_id += 1

    # CI/CD (2 VMs)
    for name in ["jenkins", "gitlab-runner"]:
        vms.append(VM(
            id=f"vm{vm_id}", name=name,
            cpu_cores=4, memory_gb=8, storage_gb=80,
            priority=2
        ))
        vm_id += 1

    # Dev/test VMs (6 VMs, lower priority)
    for i in range(6):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"dev-{i+1:02d}",
            cpu_cores=2, memory_gb=4, storage_gb=30,
            priority=1
        ))
        vm_id += 1

    return VMPlacementPlan(name="MEDIUM", servers=servers, vms=vms)


def _generate_large() -> VMPlacementPlan:
    """
    Large demo: 20 servers, 100 VMs
    - Stress test scenario
    - Multiple racks for anti-affinity
    """
    servers = []
    server_id = 1
    racks = ["rack-a", "rack-b", "rack-c", "rack-d"]

    # Large servers (8)
    for i in range(8):
        servers.append(Server(
            id=f"s{server_id}", name=f"server-large-{i+1:02d}",
            cpu_cores=48, memory_gb=192, storage_gb=2000,
            rack=racks[i % len(racks)]
        ))
        server_id += 1

    # Medium servers (8)
    for i in range(8):
        servers.append(Server(
            id=f"s{server_id}", name=f"server-medium-{i+1:02d}",
            cpu_cores=24, memory_gb=96, storage_gb=1000,
            rack=racks[i % len(racks)]
        ))
        server_id += 1

    # Small servers (4)
    for i in range(4):
        servers.append(Server(
            id=f"s{server_id}", name=f"server-small-{i+1:02d}",
            cpu_cores=12, memory_gb=48, storage_gb=500,
            rack=racks[i % len(racks)]
        ))
        server_id += 1

    vms = []
    vm_id = 1

    # Web tier (12 VMs, affinity)
    for i in range(12):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"web-{i+1:02d}",
            cpu_cores=2, memory_gb=4, storage_gb=20,
            priority=3, affinity_group="web-tier"
        ))
        vm_id += 1

    # Database clusters (2 clusters, 3 VMs each, anti-affinity)
    for cluster in range(2):
        for i in range(3):
            role = "primary" if i == 0 else f"replica-{i}"
            vms.append(VM(
                id=f"vm{vm_id}", name=f"db-cluster{cluster+1}-{role}",
                cpu_cores=8, memory_gb=32, storage_gb=300,
                priority=5, anti_affinity_group=f"db-cluster-{cluster+1}"
            ))
            vm_id += 1

    # API servers (16 VMs)
    for i in range(16):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"api-{i+1:02d}",
            cpu_cores=4, memory_gb=8, storage_gb=50,
            priority=4
        ))
        vm_id += 1

    # Cache tier (8 VMs, affinity)
    for i in range(8):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"cache-{i+1:02d}",
            cpu_cores=4, memory_gb=24, storage_gb=30,
            priority=3, affinity_group="cache-tier"
        ))
        vm_id += 1

    # Worker nodes (24 VMs)
    for i in range(24):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"worker-{i+1:02d}",
            cpu_cores=2, memory_gb=4, storage_gb=40,
            priority=2
        ))
        vm_id += 1

    # Message queue cluster (3 VMs, anti-affinity)
    for i in range(3):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"kafka-{i+1:02d}",
            cpu_cores=4, memory_gb=16, storage_gb=200,
            priority=4, anti_affinity_group="kafka-cluster"
        ))
        vm_id += 1

    # Search cluster (5 VMs, anti-affinity)
    for i in range(5):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"elasticsearch-{i+1:02d}",
            cpu_cores=6, memory_gb=24, storage_gb=250,
            priority=3, anti_affinity_group="search-cluster"
        ))
        vm_id += 1

    # Monitoring stack (6 VMs)
    for name in ["prometheus", "grafana", "alertmanager", "thanos-query", "thanos-store", "thanos-compact"]:
        vms.append(VM(
            id=f"vm{vm_id}", name=name,
            cpu_cores=4, memory_gb=8, storage_gb=100,
            priority=3
        ))
        vm_id += 1

    # CI/CD (4 VMs)
    for name in ["jenkins-master", "jenkins-agent-1", "jenkins-agent-2", "artifact-repo"]:
        vms.append(VM(
            id=f"vm{vm_id}", name=name,
            cpu_cores=4, memory_gb=8, storage_gb=120,
            priority=2
        ))
        vm_id += 1

    # Dev/test VMs (10 VMs, lower priority)
    for i in range(10):
        vms.append(VM(
            id=f"vm{vm_id}", name=f"dev-{i+1:02d}",
            cpu_cores=2, memory_gb=4, storage_gb=30,
            priority=1
        ))
        vm_id += 1

    return VMPlacementPlan(name="LARGE", servers=servers, vms=vms)
