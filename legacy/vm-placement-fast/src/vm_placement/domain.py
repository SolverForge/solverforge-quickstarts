from solverforge_legacy.solver import SolverStatus
from solverforge_legacy.solver.score import HardSoftScore
from solverforge_legacy.solver.domain import (
    planning_entity,
    planning_solution,
    PlanningId,
    PlanningScore,
    PlanningVariable,
    PlanningEntityCollectionProperty,
    ProblemFactCollectionProperty,
    ValueRangeProvider,
)

from typing import Annotated, Optional, List, Union
from dataclasses import dataclass, field
from .json_serialization import (
    JsonDomainBase,
    IdSerializer,
    IdListSerializer,
    VMListValidator,
    ServerValidator,
)
from pydantic import Field


@dataclass
class Server:
    """
    A physical server that can host virtual machines.

    Servers have capacity limits for CPU cores, memory (GB), and storage (GB).
    This is a problem fact - it doesn't change during solving.
    """

    id: Annotated[str, PlanningId]
    name: str
    cpu_cores: int
    memory_gb: int
    storage_gb: int
    rack: Optional[str] = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"Server({self.id}, {self.name})"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Server):
            return False
        return self.id == other.id


@planning_entity
@dataclass
class VM:
    """
    A virtual machine that needs to be placed on a server.

    VMs have resource requirements (CPU, memory, storage) and optional
    affinity/anti-affinity constraints for placement.
    The server field is the planning variable that the solver optimizes.
    """

    id: Annotated[str, PlanningId]
    name: str
    cpu_cores: int
    memory_gb: int
    storage_gb: int
    priority: int = 1
    affinity_group: Optional[str] = None
    anti_affinity_group: Optional[str] = None
    server: Annotated[Optional[Server], PlanningVariable] = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"VM({self.id}, {self.name})"


@planning_solution
@dataclass
class VMPlacementPlan:
    """
    The planning solution containing all servers and VMs.

    The solver will assign VMs to servers while respecting capacity constraints,
    affinity/anti-affinity rules, and optimizing for consolidation and balance.
    """

    name: str
    servers: Annotated[list[Server], ProblemFactCollectionProperty, ValueRangeProvider]
    vms: Annotated[list[VM], PlanningEntityCollectionProperty]
    score: Annotated[Optional[HardSoftScore], PlanningScore] = None
    solver_status: SolverStatus = SolverStatus.NOT_SOLVING

    def get_vms_on_server(self, server: Server) -> list:
        """Get all VMs assigned to a specific server."""
        return [vm for vm in self.vms if vm.server == server]

    def get_server_used_cpu(self, server: Server) -> int:
        """Get total CPU cores used on a server."""
        return sum(vm.cpu_cores for vm in self.vms if vm.server == server)

    def get_server_used_memory(self, server: Server) -> int:
        """Get total memory (GB) used on a server."""
        return sum(vm.memory_gb for vm in self.vms if vm.server == server)

    def get_server_used_storage(self, server: Server) -> int:
        """Get total storage (GB) used on a server."""
        return sum(vm.storage_gb for vm in self.vms if vm.server == server)

    @property
    def total_servers(self) -> int:
        return len(self.servers)

    @property
    def active_servers(self) -> int:
        active_server_ids = set(vm.server.id for vm in self.vms if vm.server is not None)
        return len(active_server_ids)

    @property
    def unassigned_vms(self) -> int:
        return sum(1 for vm in self.vms if vm.server is None)

    @property
    def total_cpu_utilization(self) -> float:
        total_capacity = sum(s.cpu_cores for s in self.servers)
        total_used = sum(vm.cpu_cores for vm in self.vms if vm.server is not None)
        if total_capacity == 0:
            return 0.0
        return total_used / total_capacity

    @property
    def total_memory_utilization(self) -> float:
        total_capacity = sum(s.memory_gb for s in self.servers)
        total_used = sum(vm.memory_gb for vm in self.vms if vm.server is not None)
        if total_capacity == 0:
            return 0.0
        return total_used / total_capacity

    @property
    def total_storage_utilization(self) -> float:
        total_capacity = sum(s.storage_gb for s in self.servers)
        total_used = sum(vm.storage_gb for vm in self.vms if vm.server is not None)
        if total_capacity == 0:
            return 0.0
        return total_used / total_capacity

    def __str__(self):
        return f"VMPlacementPlan(name={self.name}, servers={len(self.servers)}, vms={len(self.vms)})"


# Pydantic REST models for API (used for deserialization and context)
class VMModel(JsonDomainBase):
    id: str
    name: str
    cpu_cores: int = Field(..., alias="cpuCores")
    memory_gb: int = Field(..., alias="memoryGb")
    storage_gb: int = Field(..., alias="storageGb")
    priority: int = 1
    affinity_group: Optional[str] = Field(None, alias="affinityGroup")
    anti_affinity_group: Optional[str] = Field(None, alias="antiAffinityGroup")
    server: Annotated[
        Union[str, "ServerModel", None],
        IdSerializer,
        ServerValidator,
    ] = None


class ServerModel(JsonDomainBase):
    id: str
    name: str
    cpu_cores: int = Field(..., alias="cpuCores")
    memory_gb: int = Field(..., alias="memoryGb")
    storage_gb: int = Field(..., alias="storageGb")
    rack: Optional[str] = None
    vms: Annotated[
        List[Union[str, VMModel]],
        IdListSerializer,
        VMListValidator,
    ] = Field(default_factory=list)
    used_cpu: int = Field(0, alias="usedCpu")
    used_memory: int = Field(0, alias="usedMemory")
    used_storage: int = Field(0, alias="usedStorage")
    cpu_utilization: float = Field(0.0, alias="cpuUtilization")
    memory_utilization: float = Field(0.0, alias="memoryUtilization")
    storage_utilization: float = Field(0.0, alias="storageUtilization")


class VMPlacementPlanModel(JsonDomainBase):
    name: str
    servers: List[ServerModel]
    vms: List[VMModel]
    score: Optional[str] = None
    solver_status: Optional[str] = Field(None, alias="solverStatus")
    total_servers: int = Field(0, alias="totalServers")
    active_servers: int = Field(0, alias="activeServers")
    unassigned_vms: int = Field(0, alias="unassignedVms")
    total_cpu_utilization: float = Field(0.0, alias="totalCpuUtilization")
    total_memory_utilization: float = Field(0.0, alias="totalMemoryUtilization")
    total_storage_utilization: float = Field(0.0, alias="totalStorageUtilization")
