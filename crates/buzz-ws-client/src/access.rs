//! Cloudflare Access service-token headers for HTTPS and WebSocket clients.
//!
//! Access sits in front of an extra hostname (for example
//! `buzz.middlewaylabs.com`). A machine client without a browser session sends
//! `CF-Access-Client-Id` and `CF-Access-Client-Secret` on every request and on
//! the WebSocket upgrade. The values are never written into error strings.

use tokio_tungstenite::tungstenite::http::{HeaderMap, HeaderName, HeaderValue};

use crate::error::WsClientError;

/// Header Cloudflare Access expects for a service-token client id.
pub const CF_ACCESS_CLIENT_ID_HEADER: HeaderName = HeaderName::from_static("cf-access-client-id");
/// Header Cloudflare Access expects for a service-token client secret.
pub const CF_ACCESS_CLIENT_SECRET_HEADER: HeaderName =
    HeaderName::from_static("cf-access-client-secret");

const ID_ENV: &[&str] = &["BUZZ_CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_ID"];
const SECRET_ENV: &[&str] = &["BUZZ_CF_ACCESS_CLIENT_SECRET", "CF_ACCESS_CLIENT_SECRET"];

/// Load Access service-token headers from the process environment.
///
/// Both id and secret must be set together. Neither set returns an empty map
/// (Tailscale and local relays stay unchanged). One without the other is a
/// configuration error.
pub fn cloudflare_access_headers_from_env() -> Result<HeaderMap, WsClientError> {
    cloudflare_access_headers(first_nonempty_env(ID_ENV), first_nonempty_env(SECRET_ENV))
}

/// Build Access headers from already-read id and secret strings.
pub fn cloudflare_access_headers(
    client_id: Option<String>,
    client_secret: Option<String>,
) -> Result<HeaderMap, WsClientError> {
    match (client_id, client_secret) {
        (None, None) => Ok(HeaderMap::new()),
        (Some(_), None) | (None, Some(_)) => Err(WsClientError::Config(
            "Cloudflare Access service token needs both BUZZ_CF_ACCESS_CLIENT_ID and \
             BUZZ_CF_ACCESS_CLIENT_SECRET (or CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET)"
                .into(),
        )),
        (Some(id), Some(secret)) => {
            let mut headers = HeaderMap::new();
            headers.insert(CF_ACCESS_CLIENT_ID_HEADER, sensitive_header(&id)?);
            headers.insert(CF_ACCESS_CLIENT_SECRET_HEADER, sensitive_header(&secret)?);
            Ok(headers)
        }
    }
}

/// Merge Access env headers under `headers` so caller values win on clash.
pub fn merge_cloudflare_access_headers(headers: HeaderMap) -> Result<HeaderMap, WsClientError> {
    let mut merged = cloudflare_access_headers_from_env()?;
    for (name, value) in headers {
        if let Some(name) = name {
            merged.insert(name, value);
        }
    }
    Ok(merged)
}

fn first_nonempty_env(names: &[&str]) -> Option<String> {
    names.iter().find_map(|name| {
        std::env::var(name)
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty())
    })
}

fn sensitive_header(value: &str) -> Result<HeaderValue, WsClientError> {
    let mut header = HeaderValue::from_str(value).map_err(|_| {
        WsClientError::Config(
            "Cloudflare Access service token is not a valid HTTP header value".into(),
        )
    })?;
    header.set_sensitive(true);
    Ok(header)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn neither_set_is_empty() {
        let headers = cloudflare_access_headers(None, None).expect("empty is ok");
        assert!(headers.is_empty());
    }

    #[test]
    fn one_sided_is_config_error() {
        assert!(cloudflare_access_headers(Some("id".into()), None).is_err());
        assert!(cloudflare_access_headers(None, Some("secret".into())).is_err());
    }

    #[test]
    fn both_set_are_sensitive() {
        let headers =
            cloudflare_access_headers(Some("client-id".into()), Some("client-secret".into()))
                .expect("pair");
        let id = headers.get(CF_ACCESS_CLIENT_ID_HEADER).expect("id");
        let secret = headers.get(CF_ACCESS_CLIENT_SECRET_HEADER).expect("secret");
        assert_eq!(id.as_bytes(), b"client-id");
        assert_eq!(secret.as_bytes(), b"client-secret");
        assert!(id.is_sensitive());
        assert!(secret.is_sensitive());
        assert!(!format!("{secret:?}").contains("client-secret"));
    }

    #[test]
    fn caller_headers_overwrite_access_on_clash() {
        let mut caller = HeaderMap::new();
        caller.insert(
            CF_ACCESS_CLIENT_ID_HEADER,
            HeaderValue::from_static("caller-id"),
        );
        let mut merged =
            cloudflare_access_headers(Some("env-id".into()), Some("env-secret".into()))
                .expect("pair");
        for (name, value) in caller {
            if let Some(name) = name {
                merged.insert(name, value);
            }
        }
        assert_eq!(
            merged.get(CF_ACCESS_CLIENT_ID_HEADER).unwrap().as_bytes(),
            b"caller-id"
        );
    }
}
