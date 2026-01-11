from . import domain


# Conversion functions from domain to API models
def vm_to_model(vm: domain.VM) -> domain.VMModel:
    # Handle both Server objects and string IDs
    server_id = None
    if vm.server:
        server_id = vm.server if isinstance(vm.server, str) else vm.server.id
    return domain.VMModel(
        id=vm.id,
        name=vm.name,
        cpu_cores=vm.cpu_cores,
        memory_gb=vm.memory_gb,
        storage_gb=vm.storage_gb,
        priority=vm.priority,
        affinity_group=vm.affinity_group,
        anti_affinity_group=vm.anti_affinity_group,
        server=server_id,
    )


def server_to_model(server: domain.Server, plan: domain.VMPlacementPlan) -> domain.ServerModel:
    """Convert a Server to ServerModel, computing VM assignments from the plan."""
    # Get VMs assigned to this server
    vms_on_server = [vm for vm in plan.vms if vm.server == server]
    vm_ids = [vm.id for vm in vms_on_server]

    # Compute utilization
    used_cpu = sum(vm.cpu_cores for vm in vms_on_server)
    used_memory = sum(vm.memory_gb for vm in vms_on_server)
    used_storage = sum(vm.storage_gb for vm in vms_on_server)

    cpu_utilization = used_cpu / server.cpu_cores if server.cpu_cores > 0 else 0.0
    memory_utilization = used_memory / server.memory_gb if server.memory_gb > 0 else 0.0
    storage_utilization = used_storage / server.storage_gb if server.storage_gb > 0 else 0.0

    return domain.ServerModel(
        id=server.id,
        name=server.name,
        cpu_cores=server.cpu_cores,
        memory_gb=server.memory_gb,
        storage_gb=server.storage_gb,
        rack=server.rack,
        vms=vm_ids,
        used_cpu=used_cpu,
        used_memory=used_memory,
        used_storage=used_storage,
        cpu_utilization=cpu_utilization,
        memory_utilization=memory_utilization,
        storage_utilization=storage_utilization,
    )


def plan_to_model(plan: domain.VMPlacementPlan) -> domain.VMPlacementPlanModel:
    return domain.VMPlacementPlanModel(
        name=plan.name,
        servers=[server_to_model(s, plan) for s in plan.servers],
        vms=[vm_to_model(vm) for vm in plan.vms],
        score=str(plan.score) if plan.score else None,
        solver_status=plan.solver_status.name if plan.solver_status else None,
        total_servers=plan.total_servers,
        active_servers=plan.active_servers,
        unassigned_vms=plan.unassigned_vms,
        total_cpu_utilization=plan.total_cpu_utilization,
        total_memory_utilization=plan.total_memory_utilization,
        total_storage_utilization=plan.total_storage_utilization,
    )


# Conversion functions from API models to domain
def model_to_vm(model: domain.VMModel, server_lookup: dict) -> domain.VM:
    server = None
    if model.server:
        if isinstance(model.server, str):
            server = server_lookup.get(model.server)
        else:
            server = server_lookup.get(model.server.id)

    return domain.VM(
        id=model.id,
        name=model.name,
        cpu_cores=model.cpu_cores,
        memory_gb=model.memory_gb,
        storage_gb=model.storage_gb,
        priority=model.priority,
        affinity_group=model.affinity_group,
        anti_affinity_group=model.anti_affinity_group,
        server=server,
    )


def model_to_server(model: domain.ServerModel) -> domain.Server:
    """Convert ServerModel to Server (Server no longer has vms list)."""
    return domain.Server(
        id=model.id,
        name=model.name,
        cpu_cores=model.cpu_cores,
        memory_gb=model.memory_gb,
        storage_gb=model.storage_gb,
        rack=model.rack,
    )


def model_to_plan(model: domain.VMPlacementPlanModel) -> domain.VMPlacementPlan:
    # Convert servers first
    servers = []
    for server_model in model.servers:
        server = domain.Server(
            id=server_model.id,
            name=server_model.name,
            cpu_cores=server_model.cpu_cores,
            memory_gb=server_model.memory_gb,
            storage_gb=server_model.storage_gb,
            rack=server_model.rack,
        )
        servers.append(server)

    # Create server lookup
    server_lookup = {s.id: s for s in servers}

    # Convert VMs with server references
    vms = []
    for vm_model in model.vms:
        # Get server reference from VM's server field
        server = None
        if vm_model.server:
            server_id = vm_model.server if isinstance(vm_model.server, str) else vm_model.server.id
            server = server_lookup.get(server_id)

        vm = domain.VM(
            id=vm_model.id,
            name=vm_model.name,
            cpu_cores=vm_model.cpu_cores,
            memory_gb=vm_model.memory_gb,
            storage_gb=vm_model.storage_gb,
            priority=vm_model.priority,
            affinity_group=vm_model.affinity_group,
            anti_affinity_group=vm_model.anti_affinity_group,
            server=server,
        )
        vms.append(vm)

    # Handle score
    score = None
    if model.score:
        from solverforge_legacy.solver.score import HardSoftScore
        score = HardSoftScore.parse(model.score)

    # Handle solver status
    solver_status = domain.SolverStatus.NOT_SOLVING
    if model.solver_status:
        solver_status = domain.SolverStatus[model.solver_status]

    return domain.VMPlacementPlan(
        name=model.name,
        servers=servers,
        vms=vms,
        score=score,
        solver_status=solver_status,
    )
