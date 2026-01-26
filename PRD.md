# Project: Fix Helm Charts and Dockerfiles for ArgoCD Deployment

Fix GHCR image visibility, add missing health endpoints, create Helm charts for Rust vehicle-routing apps, and update CI/CD pipeline.

## Tasks

### Phase 1: Add Health Endpoints to Rust Apps
- [x] Add `/healthz` route alias to vehicle-routing API (rust/vehicle-routing/src/api.rs)
- [x] Add `/healthz` route alias to vehicle-routing-rust-pre API (rust/vehicle-routing-rust-pre/src/api.rs)

### Phase 2: Create Dockerfile for vehicle-routing
- [x] Create Dockerfile for rust/vehicle-routing following employee-scheduling pattern (rust/vehicle-routing/Dockerfile)

### Phase 3: Create Helm Chart for vehicle-routing
- [x] Create Chart.yaml for vehicle-routing (rust/vehicle-routing/helm/vehicle-routing/Chart.yaml)
- [x] Create values.yaml with probes on /healthz port 7860 (rust/vehicle-routing/helm/vehicle-routing/values.yaml)
- [x] Create _helpers.tpl template (rust/vehicle-routing/helm/vehicle-routing/templates/_helpers.tpl)
- [x] Create deployment.yaml template (rust/vehicle-routing/helm/vehicle-routing/templates/deployment.yaml)
- [x] Create service.yaml template (rust/vehicle-routing/helm/vehicle-routing/templates/service.yaml)
- [x] Create ingress.yaml template (rust/vehicle-routing/helm/vehicle-routing/templates/ingress.yaml)

### Phase 4: Create Helm Chart for vehicle-routing-pre
- [x] Create Chart.yaml for vehicle-routing-pre (rust/vehicle-routing-rust-pre/helm/vehicle-routing-pre/Chart.yaml)
- [x] Create values.yaml with probes on /healthz port 7860 (rust/vehicle-routing-rust-pre/helm/vehicle-routing-pre/values.yaml)
- [x] Create _helpers.tpl template (rust/vehicle-routing-rust-pre/helm/vehicle-routing-pre/templates/_helpers.tpl)
- [x] Create deployment.yaml template (rust/vehicle-routing-rust-pre/helm/vehicle-routing-pre/templates/deployment.yaml)
- [x] Create service.yaml template (rust/vehicle-routing-rust-pre/helm/vehicle-routing-pre/templates/service.yaml)
- [x] Create ingress.yaml template (rust/vehicle-routing-rust-pre/helm/vehicle-routing-pre/templates/ingress.yaml)

### Phase 5: Update CI/CD Pipeline
- [x] Add vehicle-routing and vehicle-routing-pre to matrix in docker-publish.yml (.github/workflows/docker-publish.yml)
- [x] Add paths triggers for rust/vehicle-routing/** and rust/vehicle-routing-rust-pre/** (.github/workflows/docker-publish.yml)
- [x] Add step to make images public after push (.github/workflows/docker-publish.yml)

### Phase 6: Verification
- [ ] Build vehicle-routing Docker image locally (BLOCKED: requires solverforge 0.6.0+ on crates.io - current code uses unreleased API)
- [x] Build vehicle-routing-pre Docker image locally
- [ ] Lint vehicle-routing Helm chart
- [ ] Lint vehicle-routing-pre Helm chart

## Notes

- All apps use port 7860 (HF Spaces default)
- Health probes must target `/healthz` on named port `http`
- Use employee-scheduling as reference for Dockerfile and Helm chart patterns
- Image repositories: `ghcr.io/solverforge/vehicle-routing` and `ghcr.io/solverforge/vehicle-routing-pre`
- vehicle-routing-rust-pre already has a Dockerfile; only vehicle-routing needs one created
- Making images public requires `packages:write` permission (already present in workflow)
- The `gh api` call to set visibility may need `GITHUB_TOKEN` with appropriate permissions
- **vehicle-routing Docker build blocker**: The app code uses a newer solverforge API (ScoreDirector, constraint builders) that isn't published to crates.io yet. The build will work once solverforge 0.6.0+ is published.

## Success Criteria

- All checkboxes marked `[x]`
- `docker build` succeeds for both vehicle-routing apps
- `helm lint` passes for both new Helm charts
- `helm template` renders valid Kubernetes manifests
- Health endpoints return `{"status":"UP"}` on `/healthz`
