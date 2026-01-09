//! Solver service for Vehicle Routing Problem.

use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::oneshot;
use tracing::info;

use crate::domain::VehicleRoutePlan;

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SolverStatus {
    NotSolving,
    Solving,
}

pub struct SolveJob {
    pub id: String,
    pub status: SolverStatus,
    pub plan: VehicleRoutePlan,
    stop_signal: Option<oneshot::Sender<()>>,
}

pub struct SolverService {
    jobs: RwLock<HashMap<String, Arc<RwLock<SolveJob>>>>,
}

impl SolverService {
    pub fn new() -> Self {
        Self { jobs: RwLock::new(HashMap::new()) }
    }

    pub fn create_job(&self, id: String, plan: VehicleRoutePlan) -> Arc<RwLock<SolveJob>> {
        let job = Arc::new(RwLock::new(SolveJob {
            id: id.clone(),
            status: SolverStatus::NotSolving,
            plan,
            stop_signal: None,
        }));
        self.jobs.write().insert(id, job.clone());
        job
    }

    pub fn get_job(&self, id: &str) -> Option<Arc<RwLock<SolveJob>>> {
        self.jobs.read().get(id).cloned()
    }

    pub fn remove_job(&self, id: &str) -> Option<Arc<RwLock<SolveJob>>> {
        self.jobs.write().remove(id)
    }

    pub fn start_solving(&self, job: Arc<RwLock<SolveJob>>) {
        let (tx, rx) = oneshot::channel();
        {
            let mut guard = job.write();
            guard.status = SolverStatus::Solving;
            guard.stop_signal = Some(tx);
        }

        let job_clone = job.clone();
        tokio::task::spawn_blocking(move || solve_blocking(job_clone, rx));
    }

    pub fn stop_solving(&self, id: &str) -> bool {
        if let Some(job) = self.get_job(id) {
            let mut guard = job.write();
            if let Some(signal) = guard.stop_signal.take() {
                let _ = signal.send(());
                guard.status = SolverStatus::NotSolving;
                return true;
            }
        }
        false
    }
}

fn solve_blocking(job: Arc<RwLock<SolveJob>>, mut stop_rx: oneshot::Receiver<()>) {
    let solution = job.read().plan.clone();
    let job_id = job.read().id.clone();
    let start = Instant::now();

    info!(job_id = %job_id, "Starting solver");

    // External cancellation signal (user stops solving)
    // Time limit comes from solver.toml, not hardcoded here
    let terminate = Arc::new(AtomicBool::new(false));
    let terminate_clone = terminate.clone();

    std::thread::spawn(move || {
        loop {
            if stop_rx.try_recv().is_ok() {
                terminate_clone.store(true, Ordering::SeqCst);
                break;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    });

    let result = solution.solve_with_terminate(Some(terminate));

    info!(job_id = %job_id, duration = ?start.elapsed(), score = ?result.score, "Solving complete");

    let mut guard = job.write();
    guard.plan = result;
    guard.status = SolverStatus::NotSolving;
}
