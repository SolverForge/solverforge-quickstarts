//! Vehicle Routing Quickstart - Axum Server
//!
//! Run with: cargo run -p vehicle-routing
//! Then open: http://localhost:7860

use std::net::SocketAddr;
use std::path::PathBuf;
use tower_http::cors::{Any, CorsLayer};
use tower_http::services::ServeDir;

use vehicle_routing::api;

#[tokio::main]
async fn main() {
    solverforge::console::init();

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let static_path = if PathBuf::from("examples/vehicle-routing/static").exists() {
        "examples/vehicle-routing/static"
    } else {
        "static"
    };

    let app = api::router()
        .fallback_service(ServeDir::new(static_path))
        .layer(cors);

    let addr = SocketAddr::from(([0, 0, 0, 0], 7860));

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    println!("Server running at http://localhost:{}", addr.port());
    axum::serve(listener, app).await.unwrap();
}
