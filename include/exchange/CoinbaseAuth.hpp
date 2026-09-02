#pragma once

#include <cstdint>
#include <string>

namespace trade {
namespace exchange {

// Pure request-signing helpers for the Coinbase Advanced Trade API.
// Two credential generations are supported:
//  - CDP keys: the secret is an EC (P-256) private key PEM; requests carry an
//    ES256 JWT bearer token.
//  - Legacy keys: the secret is an opaque string; requests carry
//    CB-ACCESS-KEY / CB-ACCESS-SIGN (hex HMAC-SHA256) / CB-ACCESS-TIMESTAMP.

std::string base64UrlEncode(const unsigned char *data, std::size_t length);
std::string base64UrlEncode(const std::string &data);

std::string hmacSha256Hex(const std::string &secret, const std::string &message);

// True when the secret looks like a PEM EC private key (CDP-generation key).
bool secretIsEcPrivateKeyPem(const std::string &secret);

// Normalizes literal "\n" sequences (common in env files) into real newlines.
std::string normalizePemNewlines(const std::string &pem);

// Builds the ES256 JWT for one request. `uri` must be
// "<METHOD> <host><path>", e.g. "GET api.coinbase.com/api/v3/brokerage/accounts".
// Returns an empty string (and sets *error when provided) on signing failure.
std::string buildEs256Jwt(const std::string &key_name, const std::string &ec_private_key_pem,
                          const std::string &uri, long long issued_at_epoch_seconds,
                          const std::string &nonce_hex, std::string *error = nullptr);

} // namespace exchange
} // namespace trade
