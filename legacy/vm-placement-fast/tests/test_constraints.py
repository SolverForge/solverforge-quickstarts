from solverforge_legacy.solver.test import ConstraintVerifier

from vm_placement.domain import Server, VM, VMPlacementPlan
from vm_placement.constraints import (
    define_constraints,
    cpu_capacity,
    memory_capacity,
    storage_capacity,
    anti_affinity,
    affinity,
    minimize_servers_used,
    balance_utilization,
    prioritize_placement,
)

# VM is the only planning entity (Server is a problem fact)
constraint_verifier = ConstraintVerifier.build(
    define_constraints, VMPlacementPlan, VM
)


def assign(server: Server, *vms: VM):
    """Helper to assign VMs to a server."""
    for vm in vms:
        vm.server = server


##############################################
# CPU Capacity Tests
##############################################


def test_cpu_capacity_not_exceeded():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=4, memory_gb=8, storage_gb=50)
    vm2 = VM(id="vm2", name="VM2", cpu_cores=8, memory_gb=16, storage_gb=100)
    assign(server, vm1, vm2)

    (
        constraint_verifier.verify_that(cpu_capacity)
        .given(server, vm1, vm2)
        .penalizes_by(0)
    )


def test_cpu_capacity_exceeded():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=12, memory_gb=8, storage_gb=50)
    vm2 = VM(id="vm2", name="VM2", cpu_cores=8, memory_gb=16, storage_gb=100)
    assign(server, vm1, vm2)

    # 12 + 8 = 20 cores, capacity = 16, excess = 4
    (
        constraint_verifier.verify_that(cpu_capacity)
        .given(server, vm1, vm2)
        .penalizes_by(4)
    )


##############################################
# Memory Capacity Tests
##############################################


def test_memory_capacity_not_exceeded():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=4, memory_gb=32, storage_gb=50)
    vm2 = VM(id="vm2", name="VM2", cpu_cores=4, memory_gb=16, storage_gb=100)
    assign(server, vm1, vm2)

    (
        constraint_verifier.verify_that(memory_capacity)
        .given(server, vm1, vm2)
        .penalizes_by(0)
    )


def test_memory_capacity_exceeded():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=4, memory_gb=48, storage_gb=50)
    vm2 = VM(id="vm2", name="VM2", cpu_cores=4, memory_gb=32, storage_gb=100)
    assign(server, vm1, vm2)

    # 48 + 32 = 80 GB, capacity = 64, excess = 16
    (
        constraint_verifier.verify_that(memory_capacity)
        .given(server, vm1, vm2)
        .penalizes_by(16)
    )


##############################################
# Storage Capacity Tests
##############################################


def test_storage_capacity_not_exceeded():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=4, memory_gb=8, storage_gb=200)
    vm2 = VM(id="vm2", name="VM2", cpu_cores=4, memory_gb=16, storage_gb=250)
    assign(server, vm1, vm2)

    (
        constraint_verifier.verify_that(storage_capacity)
        .given(server, vm1, vm2)
        .penalizes_by(0)
    )


def test_storage_capacity_exceeded():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=4, memory_gb=8, storage_gb=300)
    vm2 = VM(id="vm2", name="VM2", cpu_cores=4, memory_gb=16, storage_gb=300)
    assign(server, vm1, vm2)

    # 300 + 300 = 600 GB, capacity = 500, excess = 100
    (
        constraint_verifier.verify_that(storage_capacity)
        .given(server, vm1, vm2)
        .penalizes_by(100)
    )


##############################################
# Anti-Affinity Tests
##############################################


def test_anti_affinity_satisfied():
    server1 = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    server2 = Server(id="s2", name="Server2", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(
        id="vm1", name="DB-Primary", cpu_cores=4, memory_gb=8, storage_gb=50,
        anti_affinity_group="db-replicas"
    )
    vm2 = VM(
        id="vm2", name="DB-Replica", cpu_cores=4, memory_gb=8, storage_gb=50,
        anti_affinity_group="db-replicas"
    )
    assign(server1, vm1)
    assign(server2, vm2)

    (
        constraint_verifier.verify_that(anti_affinity)
        .given(server1, server2, vm1, vm2)
        .penalizes_by(0)
    )


def test_anti_affinity_violated():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(
        id="vm1", name="DB-Primary", cpu_cores=4, memory_gb=8, storage_gb=50,
        anti_affinity_group="db-replicas"
    )
    vm2 = VM(
        id="vm2", name="DB-Replica", cpu_cores=4, memory_gb=8, storage_gb=50,
        anti_affinity_group="db-replicas"
    )
    assign(server, vm1, vm2)

    # Both VMs on same server with same anti-affinity group = 1 violation
    (
        constraint_verifier.verify_that(anti_affinity)
        .given(server, vm1, vm2)
        .penalizes_by(1)
    )


def test_anti_affinity_no_group():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=4, memory_gb=8, storage_gb=50)
    vm2 = VM(id="vm2", name="VM2", cpu_cores=4, memory_gb=8, storage_gb=50)
    assign(server, vm1, vm2)

    # No anti-affinity group, so no penalty
    (
        constraint_verifier.verify_that(anti_affinity)
        .given(server, vm1, vm2)
        .penalizes_by(0)
    )


##############################################
# Affinity Tests
##############################################


def test_affinity_satisfied():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(
        id="vm1", name="WebApp1", cpu_cores=2, memory_gb=4, storage_gb=20,
        affinity_group="web-tier"
    )
    vm2 = VM(
        id="vm2", name="WebApp2", cpu_cores=2, memory_gb=4, storage_gb=20,
        affinity_group="web-tier"
    )
    assign(server, vm1, vm2)

    (
        constraint_verifier.verify_that(affinity)
        .given(server, vm1, vm2)
        .penalizes_by(0)
    )


def test_affinity_violated():
    server1 = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    server2 = Server(id="s2", name="Server2", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(
        id="vm1", name="WebApp1", cpu_cores=2, memory_gb=4, storage_gb=20,
        affinity_group="web-tier"
    )
    vm2 = VM(
        id="vm2", name="WebApp2", cpu_cores=2, memory_gb=4, storage_gb=20,
        affinity_group="web-tier"
    )
    assign(server1, vm1)
    assign(server2, vm2)

    # VMs on different servers with same affinity group = penalty of 100
    (
        constraint_verifier.verify_that(affinity)
        .given(server1, server2, vm1, vm2)
        .penalizes_by(100)
    )


def test_affinity_no_group():
    server1 = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    server2 = Server(id="s2", name="Server2", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=2, memory_gb=4, storage_gb=20)
    vm2 = VM(id="vm2", name="VM2", cpu_cores=2, memory_gb=4, storage_gb=20)
    assign(server1, vm1)
    assign(server2, vm2)

    # No affinity group, so no penalty
    (
        constraint_verifier.verify_that(affinity)
        .given(server1, server2, vm1, vm2)
        .penalizes_by(0)
    )


##############################################
# Minimize Servers Used Tests
##############################################


def test_minimize_servers_no_active():
    server1 = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    server2 = Server(id="s2", name="Server2", cpu_cores=16, memory_gb=64, storage_gb=500)

    (
        constraint_verifier.verify_that(minimize_servers_used)
        .given(server1, server2)
        .penalizes_by(0)
    )


def test_minimize_servers_one_active():
    server1 = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    server2 = Server(id="s2", name="Server2", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=2, memory_gb=4, storage_gb=20)
    assign(server1, vm1)

    # 1 active server = 100 penalty
    (
        constraint_verifier.verify_that(minimize_servers_used)
        .given(server1, server2, vm1)
        .penalizes_by(100)
    )


def test_minimize_servers_two_active():
    server1 = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    server2 = Server(id="s2", name="Server2", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=2, memory_gb=4, storage_gb=20)
    vm2 = VM(id="vm2", name="VM2", cpu_cores=2, memory_gb=4, storage_gb=20)
    assign(server1, vm1)
    assign(server2, vm2)

    # 2 active servers = 200 penalty
    (
        constraint_verifier.verify_that(minimize_servers_used)
        .given(server1, server2, vm1, vm2)
        .penalizes_by(200)
    )


##############################################
# Balance Utilization Tests
##############################################


def test_balance_utilization_empty():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)

    (
        constraint_verifier.verify_that(balance_utilization)
        .given(server)
        .penalizes_by(0)
    )


def test_balance_utilization_50_percent():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=8, memory_gb=32, storage_gb=250)
    assign(server, vm1)

    # 50% utilization = 0.5, squared = 0.25, * 10 = 2.5, int = 2
    (
        constraint_verifier.verify_that(balance_utilization)
        .given(server, vm1)
        .penalizes_by(2)
    )


def test_balance_utilization_100_percent():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=16, memory_gb=64, storage_gb=500)
    assign(server, vm1)

    # 100% utilization = 1.0, squared = 1.0, * 10 = 10
    (
        constraint_verifier.verify_that(balance_utilization)
        .given(server, vm1)
        .penalizes_by(10)
    )


##############################################
# Prioritize Placement Tests
##############################################


def test_prioritize_placement_assigned():
    server = Server(id="s1", name="Server1", cpu_cores=16, memory_gb=64, storage_gb=500)
    vm1 = VM(id="vm1", name="VM1", cpu_cores=4, memory_gb=8, storage_gb=50, priority=5)
    assign(server, vm1)

    (
        constraint_verifier.verify_that(prioritize_placement)
        .given(server, vm1)
        .penalizes_by(0)
    )
