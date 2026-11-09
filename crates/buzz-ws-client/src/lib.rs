#![deny(unsafe_code)]

pub mod access;
pub mod connection;
pub mod error;
pub mod message;

pub use access::{
    cloudflare_access_headers, cloudflare_access_headers_from_env, merge_cloudflare_access_headers,
    CF_ACCESS_CLIENT_ID_HEADER, CF_ACCESS_CLIENT_SECRET_HEADER,
};
pub use connection::{publish_event, NostrWsConnection};
pub use error::WsClientError;
pub use message::{build_auth_event, parse_relay_message, OkResponse, RelayMessage};
pub use tokio_tungstenite::tungstenite::http::{HeaderMap, HeaderName, HeaderValue};
