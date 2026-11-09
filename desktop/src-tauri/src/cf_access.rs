//! Attach Cloudflare Access service-token headers to Desktop HTTP clients.
//!
//! Values come from `BUZZ_CF_ACCESS_CLIENT_ID` / `BUZZ_CF_ACCESS_CLIENT_SECRET`
//! (or the unprefixed Cloudflare names). Errors never include the secret.

pub fn apply_to_builder(builder: reqwest::ClientBuilder) -> Result<reqwest::ClientBuilder, String> {
    let src =
        buzz_ws_client_pkg::cloudflare_access_headers_from_env().map_err(|e| e.to_string())?;
    if src.is_empty() {
        return Ok(builder);
    }
    let mut dest = reqwest::header::HeaderMap::new();
    for (name, value) in src.iter() {
        let name = reqwest::header::HeaderName::from_bytes(name.as_str().as_bytes())
            .map_err(|e| e.to_string())?;
        let mut copied = reqwest::header::HeaderValue::from_bytes(value.as_bytes())
            .map_err(|e| e.to_string())?;
        copied.set_sensitive(value.is_sensitive());
        dest.insert(name, copied);
    }
    Ok(builder.default_headers(dest))
}

pub fn websocket_request(
    url: &str,
) -> Result<tokio_tungstenite::tungstenite::http::Request<()>, String> {
    use tokio_tungstenite::tungstenite::client::IntoClientRequest;
    let mut request = url.into_client_request().map_err(|e| e.to_string())?;
    let headers =
        buzz_ws_client_pkg::cloudflare_access_headers_from_env().map_err(|e| e.to_string())?;
    request.headers_mut().extend(headers);
    Ok(request)
}
