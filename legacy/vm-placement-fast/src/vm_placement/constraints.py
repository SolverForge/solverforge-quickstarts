from solverforge_legacy.solver.score import (
    ConstraintFactory,
    ConstraintCollectors,
    Joiners,
    HardSoftScore,
    constraint_provider,
)

from .domain import Server, VM

# Constraint names
CPU_CAPACITY = "cpuCapacity"
MEMORY_CAPACITY = "memoryCapacity"
STORAGE_CAPACITY = "storageCapacity"
ANTI_AFFINITY = "antiAffinity"
AFFINITY = "affinity"
MINIMIZE_SERVERS_USED = "minimizeServersUsed"
BALANCE_UTILIZATION = "balanceUtilization"
PRIORITIZE_PLACEMENT = "prioritizePlacement"


@constraint_provider
def define_constraints(factory: ConstraintFactory):
    return [
        # Hard constraints
        cpu_capacity(factory),
        memory_capacity(factory),
        storage_capacity(factory),
        anti_affinity(factory),
        # Soft constraints
        affinity(factory),
        minimize_servers_used(factory),
        balance_utilization(factory),
        prioritize_placement(factory),
    ]


##############################################
# Hard constraints
##############################################


def cpu_capacity(factory: ConstraintFactory):
    """
    Hard constraint: Server CPU capacity cannot be exceeded.

    Groups VMs by server and penalizes if total CPU exceeds capacity.
    """
    return (
        factory.for_each(VM)
        .filter(lambda vm: vm.server is not None)
        .group_by(lambda vm: vm.server, ConstraintCollectors.sum(lambda vm: vm.cpu_cores))
        .filter(lambda server, total_cpu: total_cpu > server.cpu_cores)
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda server, total_cpu: total_cpu - server.cpu_cores,
        )
        .as_constraint(CPU_CAPACITY)
    )


def memory_capacity(factory: ConstraintFactory):
    """
    Hard constraint: Server memory capacity cannot be exceeded.

    Groups VMs by server and penalizes if total memory exceeds capacity.
    """
    return (
        factory.for_each(VM)
        .filter(lambda vm: vm.server is not None)
        .group_by(lambda vm: vm.server, ConstraintCollectors.sum(lambda vm: vm.memory_gb))
        .filter(lambda server, total_memory: total_memory > server.memory_gb)
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda server, total_memory: total_memory - server.memory_gb,
        )
        .as_constraint(MEMORY_CAPACITY)
    )


def storage_capacity(factory: ConstraintFactory):
    """
    Hard constraint: Server storage capacity cannot be exceeded.

    Groups VMs by server and penalizes if total storage exceeds capacity.
    """
    return (
        factory.for_each(VM)
        .filter(lambda vm: vm.server is not None)
        .group_by(lambda vm: vm.server, ConstraintCollectors.sum(lambda vm: vm.storage_gb))
        .filter(lambda server, total_storage: total_storage > server.storage_gb)
        .penalize(
            HardSoftScore.ONE_HARD,
            lambda server, total_storage: total_storage - server.storage_gb,
        )
        .as_constraint(STORAGE_CAPACITY)
    )


def anti_affinity(factory: ConstraintFactory):
    """
    Hard constraint: VMs in the same anti-affinity group must be on different servers.

    This is commonly used for database replicas, redundant services, etc.
    Penalizes each pair of VMs that violate the constraint.
    """
    return (
        factory.for_each_unique_pair(
            VM,
            Joiners.equal(lambda vm: vm.anti_affinity_group),
            Joiners.equal(lambda vm: vm.server),
        )
        .filter(lambda vm1, vm2: vm1.anti_affinity_group is not None)
        .filter(lambda vm1, vm2: vm1.server is not None)
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint(ANTI_AFFINITY)
    )


##############################################
# Soft constraints
##############################################


def affinity(factory: ConstraintFactory):
    """
    Soft constraint: VMs in the same affinity group should be on the same server.

    This is commonly used for tightly coupled services that benefit from
    low-latency communication. Penalizes each pair of VMs on different servers.
    """
    return (
        factory.for_each_unique_pair(
            VM,
            Joiners.equal(lambda vm: vm.affinity_group),
        )
        .filter(lambda vm1, vm2: vm1.affinity_group is not None)
        .filter(lambda vm1, vm2: vm1.server is not None and vm2.server is not None)
        .filter(lambda vm1, vm2: vm1.server != vm2.server)
        .penalize(HardSoftScore.ONE_SOFT, lambda vm1, vm2: 100)
        .as_constraint(AFFINITY)
    )


def minimize_servers_used(factory: ConstraintFactory):
    """
    Soft constraint: Minimize the number of servers in use.

    Consolidating VMs onto fewer servers reduces power consumption,
    cooling costs, and management overhead. Each active server incurs a cost.

    Weight is lower than prioritize_placement to ensure VMs get assigned
    before optimizing for server consolidation.
    """
    return (
        factory.for_each(VM)
        .filter(lambda vm: vm.server is not None)
        .group_by(lambda vm: vm.server, ConstraintCollectors.count())
        .penalize(HardSoftScore.ONE_SOFT, lambda server, count: 100)
        .as_constraint(MINIMIZE_SERVERS_USED)
    )


def balance_utilization(factory: ConstraintFactory):
    """
    Soft constraint: Balance utilization across active servers.

    Avoids hotspots by penalizing servers with high utilization.
    Uses a squared penalty to favor balanced distribution over consolidation
    when both are possible.
    """
    return (
        factory.for_each(VM)
        .filter(lambda vm: vm.server is not None)
        .group_by(lambda vm: vm.server, ConstraintCollectors.sum(lambda vm: vm.cpu_cores))
        .penalize(
            HardSoftScore.ONE_SOFT,
            lambda server, total_cpu: int((total_cpu / server.cpu_cores) ** 2 * 10) if server.cpu_cores > 0 else 0,
        )
        .as_constraint(BALANCE_UTILIZATION)
    )


def prioritize_placement(factory: ConstraintFactory):
    """
    Soft constraint: Higher-priority VMs should be placed.

    Penalizes unassigned VMs weighted by their priority. Higher priority VMs
    incur a larger penalty when unassigned, encouraging the solver to place
    them first.

    Base penalty of 10000 ensures VMs are always placed before optimizing
    other soft constraints. Priority adds 0-5000 additional penalty.
    """
    return (
        factory.for_each(VM)
        .filter(lambda vm: vm.server is None)
        .penalize(HardSoftScore.ONE_SOFT, lambda vm: 10000 + vm.priority * 1000)
        .as_constraint(PRIORITIZE_PLACEMENT)
    )
