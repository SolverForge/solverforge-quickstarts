//! Vehicle Routing Quickstart - Axum Server

use std::net::SocketAddr;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("vehicle_routing=info".parse().unwrap()))
        .init();

    let app = vehicle_routing::api::create_router();
    let addr = SocketAddr::from(([0, 0, 0, 0], 7860));
    println!("Server listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
