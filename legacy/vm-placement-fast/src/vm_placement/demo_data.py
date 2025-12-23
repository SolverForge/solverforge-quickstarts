from enum import Enum
import random
from .domain import Server, VM, VMPlacementPlan


class DemoData(Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


def generate_custom_data(
    rack_count: int = 3,
    servers_per_rack: int = 4,
    vm_count: int = 20
) -> VMPlacementPlan:
    """
    Generate custom demo data with configurable infrastructure and workload.

    Args:
        rack_count: Number of racks (1-8)
        servers_per_rack: Number of servers per rack (2-10)
        vm_count: Number of VMs to place (5-200)
    """
    rack_count = max(1, min(8, rack_count))
    servers_per_rack = max(2, min(10, servers_per_rack))
    vm_count = max(5, min(200, vm_count))

    servers = []
    server_id = 1

    # Generate rack names
    rack_names = [f"rack-{chr(ord('a') + i)}" for i in range(rack_count)]

    # Server templates: (cpu_cores, memory_gb, storage_gb, name_prefix)
    server_templates = [
        (48, 192, 2000, "large"),
        (32, 128, 1000, "large"),
        (24, 96, 1000, "medium"),
        (16, 64, 512, "medium"),
        (12, 48, 500, "small"),
        (8, 32, 256, "small"),
    ]

    for rack_idx, rack_name in enumerate(rack_names):
        for server_idx in range(servers_per_rack):
            # Alternate between server sizes for variety
            template_idx = (rack_idx + server_idx) % len(server_templates)
            cpu, mem, storage, size = server_templates[template_idx]

            servers.append(Server(
                id=f"s{server_id}",
                name=f"srv-{size}-{server_id:02d}",
                cpu_cores=cpu,
                memory_gb=mem,
                storage_gb=storage,
                rack=rack_name
            ))
            server_id += 1

    vms = []
    vm_id = 1

    # VM templates: (cpu_cores, memory_gb, storage_gb, name_prefix, priority, group_type)
    # group_type: None, "affinity", "anti-affinity"
    vm_templates = [
        # Critical database VMs - anti-affinity for HA
        (8, 32, 200, "db", 5, "anti-affinity"),
        # API servers
        (4, 8, 50, "api", 4, None),
        # Web tier - affinity for locality
        (2, 4, 20, "web", 3, "affinity"),
        # Cache tier - affinity
        (4, 16, 30, "cache", 3, "affinity"),
        # Workers
        (2, 4, 40, "worker", 2, None),
        # Dev/test - low priority
        (2, 4, 30, "dev", 1, None),
    ]

    # Distribute VMs across templates
    template_weights = [0.08, 0.15, 0.20, 0.10, 0.32, 0.15]  # Proportions

    # Track affinity/anti-affinity group counts
    affinity_groups = {}
    anti_affinity_groups = {}

    for i in range(vm_count):
        # Pick template based on weighted distribution
        rand_val = random.random()
        cumulative = 0
        template_idx = 0
        for idx, weight in enumerate(template_weights):
            cumulative += weight
            if rand_val <= cumulative:
                template_idx = idx
                break

        cpu, mem, storage, prefix, priority, group_type = vm_templates[template_idx]

        # Determine group assignment
        affinity_group = None
        anti_affinity_group = None

        if group_type == "affinity":
            group_name = f"{prefix}-tier"
            affinity_groups[group_name] = affinity_groups.get(group_name, 0) + 1
            affinity_group = group_name
        elif group_type == "anti-affinity":
            # Create multiple anti-affinity clusters (max 3-5 VMs per cluster)
            cluster_num = anti_affinity_groups.get(prefix, 0) // 4 + 1
            group_name = f"{prefix}-cluster-{cluster_num}"
            anti_affinity_groups[prefix] = anti_affinity_groups.get(prefix, 0) + 1
            anti_affinity_group = group_name

        # Count VMs with this prefix
        count = sum(1 for v in vms if v.name.startswith(prefix)) + 1

        vms.append(VM(
            id=f"vm{vm_id}",
            name=f"{prefix}-{count:02d}",
            cpu_cores=cpu,
            memory_gb=mem,
            storage_gb=storage,
            priority=priority,
            affinity_group=affinity_group,
            anti_affinity_group=anti_affinity_group
        ))
        vm_id += 1

    total_servers = rack_count * servers_per_rack
    return VMPlacementPlan(
        name=f"CUSTOM ({total_servers} servers, {vm_count} VMs)",
        servers=servers,
        vms=vms
    )


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
