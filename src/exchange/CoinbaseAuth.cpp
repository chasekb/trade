#include "exchange/CoinbaseAuth.hpp"

#include <openssl/bio.h>
#include <openssl/ec.h>
#include <openssl/ecdsa.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/pem.h>

#include <cstring>
#include <memory>
#include <vector>

namespace trade {
namespace exchange {

namespace {

constexpr char kBase64UrlAlphabet[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

std::string jsonEscape(const std::string &value) {
  std::string out;
  out.reserve(value.size() + 8);
  for (char c : value) {
    switch (c) {
    case '"':
      out += "\\\"";
      break;
    case '\\':
      out += "\\\\";
      break;
    case '\n':
      out += "\\n";
      break;
    case '\r':
      out += "\\r";
      break;
    case '\t':
      out += "\\t";
      break;
    default:
      out += c;
    }
  }
  return out;
}

} // namespace

std::string base64UrlEncode(const unsigned char *data, std::size_t length) {
  std::string out;
  out.reserve(((length + 2) / 3) * 4);
  std::size_t i = 0;
  while (i + 2 < length) {
    const unsigned int chunk = (static_cast<unsigned int>(data[i]) << 16) |
                               (static_cast<unsigned int>(data[i + 1]) << 8) |
                               static_cast<unsigned int>(data[i + 2]);
    out += kBase64UrlAlphabet[(chunk >> 18) & 0x3F];
    out += kBase64UrlAlphabet[(chunk >> 12) & 0x3F];
    out += kBase64UrlAlphabet[(chunk >> 6) & 0x3F];
    out += kBase64UrlAlphabet[chunk & 0x3F];
    i += 3;
  }
  const std::size_t remaining = length - i;
  if (remaining == 1) {
    const unsigned int chunk = static_cast<unsigned int>(data[i]) << 16;
    out += kBase64UrlAlphabet[(chunk >> 18) & 0x3F];
    out += kBase64UrlAlphabet[(chunk >> 12) & 0x3F];
  } else if (remaining == 2) {
    const unsigned int chunk = (static_cast<unsigned int>(data[i]) << 16) |
                               (static_cast<unsigned int>(data[i + 1]) << 8);
    out += kBase64UrlAlphabet[(chunk >> 18) & 0x3F];
    out += kBase64UrlAlphabet[(chunk >> 12) & 0x3F];
    out += kBase64UrlAlphabet[(chunk >> 6) & 0x3F];
  }
  return out;
}

std::string base64UrlEncode(const std::string &data) {
  return base64UrlEncode(reinterpret_cast<const unsigned char *>(data.data()), data.size());
}

std::string hmacSha256Hex(const std::string &secret, const std::string &message) {
  unsigned char digest[EVP_MAX_MD_SIZE];
  unsigned int digest_len = 0;
  HMAC(EVP_sha256(), secret.data(), static_cast<int>(secret.size()),
       reinterpret_cast<const unsigned char *>(message.data()), message.size(), digest,
       &digest_len);

  static const char hex[] = "0123456789abcdef";
  std::string out;
  out.reserve(digest_len * 2);
  for (unsigned int i = 0; i < digest_len; ++i) {
    out += hex[(digest[i] >> 4) & 0xF];
    out += hex[digest[i] & 0xF];
  }
  return out;
}

bool secretIsEcPrivateKeyPem(const std::string &secret) {
  return secret.find("BEGIN") != std::string::npos &&
         secret.find("PRIVATE KEY") != std::string::npos;
}

std::string normalizePemNewlines(const std::string &pem) {
  std::string out;
  out.reserve(pem.size());
  for (std::size_t i = 0; i < pem.size(); ++i) {
    if (pem[i] == '\\' && i + 1 < pem.size() && pem[i + 1] == 'n') {
      out += '\n';
      ++i;
    } else {
      out += pem[i];
    }
  }
  return out;
}

std::string buildEs256Jwt(const std::string &key_name, const std::string &ec_private_key_pem,
                          const std::string &uri, long long issued_at_epoch_seconds,
                          const std::string &nonce_hex, std::string *error) {
  const std::string pem = normalizePemNewlines(ec_private_key_pem);

  std::unique_ptr<BIO, decltype(&BIO_free)> bio(
      BIO_new_mem_buf(pem.data(), static_cast<int>(pem.size())), BIO_free);
  if (!bio) {
    if (error) {
      *error = "failed to allocate key buffer";
    }
    return {};
  }

  std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)> pkey(
      PEM_read_bio_PrivateKey(bio.get(), nullptr, nullptr, nullptr), EVP_PKEY_free);
  if (!pkey) {
    if (error) {
      *error = "failed to parse EC private key PEM";
    }
    return {};
  }

  const std::string header = "{\"alg\":\"ES256\",\"kid\":\"" + jsonEscape(key_name) +
                             "\",\"nonce\":\"" + jsonEscape(nonce_hex) +
                             "\",\"typ\":\"JWT\"}";
  const std::string payload =
      "{\"iss\":\"cdp\",\"nbf\":" + std::to_string(issued_at_epoch_seconds) +
      ",\"exp\":" + std::to_string(issued_at_epoch_seconds + 120) + ",\"sub\":\"" +
      jsonEscape(key_name) + "\",\"uri\":\"" + jsonEscape(uri) + "\"}";

  const std::string signing_input = base64UrlEncode(header) + "." + base64UrlEncode(payload);

  // DER ECDSA signature over SHA-256 of the signing input.
  std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> md_ctx(EVP_MD_CTX_new(),
                                                                 EVP_MD_CTX_free);
  if (!md_ctx ||
      EVP_DigestSignInit(md_ctx.get(), nullptr, EVP_sha256(), nullptr, pkey.get()) != 1) {
    if (error) {
      *error = "failed to initialize ES256 signer";
    }
    return {};
  }

  std::size_t der_len = 0;
  if (EVP_DigestSign(md_ctx.get(), nullptr, &der_len,
                     reinterpret_cast<const unsigned char *>(signing_input.data()),
                     signing_input.size()) != 1) {
    if (error) {
      *error = "failed to size ES256 signature";
    }
    return {};
  }
  std::vector<unsigned char> der(der_len);
  if (EVP_DigestSign(md_ctx.get(), der.data(), &der_len,
                     reinterpret_cast<const unsigned char *>(signing_input.data()),
                     signing_input.size()) != 1) {
    if (error) {
      *error = "failed to produce ES256 signature";
    }
    return {};
  }
  der.resize(der_len);

  // JWT wants the raw 64-byte r||s form, not DER.
  const unsigned char *der_ptr = der.data();
  std::unique_ptr<ECDSA_SIG, decltype(&ECDSA_SIG_free)> sig(
      d2i_ECDSA_SIG(nullptr, &der_ptr, static_cast<long>(der.size())), ECDSA_SIG_free);
  if (!sig) {
    if (error) {
      *error = "failed to decode DER signature";
    }
    return {};
  }
  const BIGNUM *r = nullptr;
  const BIGNUM *s = nullptr;
  ECDSA_SIG_get0(sig.get(), &r, &s);

  unsigned char raw[64] = {0};
  if (BN_bn2binpad(r, raw, 32) != 32 || BN_bn2binpad(s, raw + 32, 32) != 32) {
    if (error) {
      *error = "failed to normalize signature components";
    }
    return {};
  }

  return signing_input + "." + base64UrlEncode(raw, sizeof(raw));
}

} // namespace exchange
} // namespace trade
