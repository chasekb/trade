#include "exchange/CoinbaseAuth.hpp"

#include <openssl/bio.h>
#include <openssl/bn.h>
#include <openssl/ec.h>
#include <openssl/ecdsa.h>
#include <openssl/evp.h>
#include <openssl/obj_mac.h>
#include <openssl/pem.h>

#include <cstring>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

using trade::exchange::base64UrlEncode;
using trade::exchange::buildEs256Jwt;
using trade::exchange::hmacSha256Hex;
using trade::exchange::normalizePemNewlines;
using trade::exchange::secretIsEcPrivateKeyPem;

namespace {

int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << std::endl;
    ++failures;
  }
}

// RFC 4648 base64url test vectors (unpadded).
void testBase64Url() {
  expect(base64UrlEncode(std::string("")) == "", "b64url empty");
  expect(base64UrlEncode(std::string("f")) == "Zg", "b64url f");
  expect(base64UrlEncode(std::string("fo")) == "Zm8", "b64url fo");
  expect(base64UrlEncode(std::string("foo")) == "Zm9v", "b64url foo");
  expect(base64UrlEncode(std::string("foob")) == "Zm9vYg", "b64url foob");
  expect(base64UrlEncode(std::string("fooba")) == "Zm9vYmE", "b64url fooba");
  expect(base64UrlEncode(std::string("foobar")) == "Zm9vYmFy", "b64url foobar");
  const unsigned char url_bytes[] = {0xfb, 0xff, 0xbf};
  expect(base64UrlEncode(url_bytes, sizeof(url_bytes)) == "-_-_",
         "b64url uses url-safe alphabet");
}

// RFC 4231 test case 2: key "Jefe", message "what do ya want for nothing?".
void testHmac() {
  expect(hmacSha256Hex("Jefe", "what do ya want for nothing?") ==
             "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843",
         "hmac-sha256 rfc4231 vector");
}

void testPemDetection() {
  expect(secretIsEcPrivateKeyPem("-----BEGIN EC PRIVATE KEY-----\nabc\n-----END EC PRIVATE KEY-----"),
         "detects PEM secret");
  expect(!secretIsEcPrivateKeyPem("plain-hmac-secret"), "rejects plain secret");
  expect(normalizePemNewlines("a\\nb") == "a\nb", "normalizes escaped newlines");
}

std::string decodeBase64Url(const std::string &input) {
  auto value_of = [](char c) -> int {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '-') return 62;
    if (c == '_') return 63;
    return -1;
  };
  std::string out;
  int buffer = 0;
  int bits = 0;
  for (char c : input) {
    const int v = value_of(c);
    if (v < 0) {
      continue;
    }
    buffer = (buffer << 6) | v;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out += static_cast<char>((buffer >> bits) & 0xFF);
    }
  }
  return out;
}

void testJwtSignatureRoundTrip() {
  // Generate an ephemeral P-256 key.
  std::unique_ptr<EVP_PKEY_CTX, decltype(&EVP_PKEY_CTX_free)> ctx(
      EVP_PKEY_CTX_new_id(EVP_PKEY_EC, nullptr), EVP_PKEY_CTX_free);
  expect(ctx != nullptr, "key ctx");
  EVP_PKEY_keygen_init(ctx.get());
  EVP_PKEY_CTX_set_ec_paramgen_curve_nid(ctx.get(), NID_X9_62_prime256v1);
  EVP_PKEY *raw_key = nullptr;
  expect(EVP_PKEY_keygen(ctx.get(), &raw_key) == 1, "keygen");
  std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)> pkey(raw_key, EVP_PKEY_free);

  // Serialize the private key to PEM, as it would arrive via env config.
  std::unique_ptr<BIO, decltype(&BIO_free)> pem_bio(BIO_new(BIO_s_mem()), BIO_free);
  expect(PEM_write_bio_PrivateKey(pem_bio.get(), pkey.get(), nullptr, nullptr, 0, nullptr,
                                  nullptr) == 1,
         "pem write");
  char *pem_data = nullptr;
  const long pem_len = BIO_get_mem_data(pem_bio.get(), &pem_data);
  const std::string pem(pem_data, static_cast<std::size_t>(pem_len));

  const std::string key_name = "organizations/test-org/apiKeys/test-key";
  const std::string uri = "GET api.coinbase.com/api/v3/brokerage/accounts";
  std::string error;
  const std::string jwt = buildEs256Jwt(key_name, pem, uri, 1750000000LL, "0123abcd", &error);
  expect(!jwt.empty(), "jwt built: " + error);
  if (jwt.empty()) {
    return;
  }

  // Structure: three dot-separated segments; header/payload carry our claims.
  const auto first_dot = jwt.find('.');
  const auto second_dot = jwt.find('.', first_dot + 1);
  expect(first_dot != std::string::npos && second_dot != std::string::npos, "jwt has 3 parts");

  const std::string header_json = decodeBase64Url(jwt.substr(0, first_dot));
  const std::string payload_json =
      decodeBase64Url(jwt.substr(first_dot + 1, second_dot - first_dot - 1));
  expect(header_json.find("\"alg\":\"ES256\"") != std::string::npos, "header alg");
  expect(header_json.find(key_name) != std::string::npos, "header kid");
  expect(payload_json.find("\"iss\":\"cdp\"") != std::string::npos, "payload iss");
  expect(payload_json.find(uri) != std::string::npos, "payload uri");
  expect(payload_json.find("\"exp\":1750000120") != std::string::npos, "payload exp = nbf+120");

  // Cryptographic verification: rebuild DER from raw r||s and verify with the
  // public half of the same key.
  const std::string signature_raw = decodeBase64Url(jwt.substr(second_dot + 1));
  expect(signature_raw.size() == 64, "raw signature is 64 bytes");
  if (signature_raw.size() != 64) {
    return;
  }

  ECDSA_SIG *sig = ECDSA_SIG_new();
  BIGNUM *r = BN_bin2bn(reinterpret_cast<const unsigned char *>(signature_raw.data()), 32, nullptr);
  BIGNUM *s =
      BN_bin2bn(reinterpret_cast<const unsigned char *>(signature_raw.data()) + 32, 32, nullptr);
  ECDSA_SIG_set0(sig, r, s);
  unsigned char *der = nullptr;
  const int der_len = i2d_ECDSA_SIG(sig, &der);
  expect(der_len > 0, "re-encode DER");

  const std::string signing_input = jwt.substr(0, second_dot);
  std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> md_ctx(EVP_MD_CTX_new(),
                                                                 EVP_MD_CTX_free);
  expect(EVP_DigestVerifyInit(md_ctx.get(), nullptr, EVP_sha256(), nullptr, pkey.get()) == 1,
         "verify init");
  const int verified = EVP_DigestVerify(
      md_ctx.get(), der, static_cast<std::size_t>(der_len),
      reinterpret_cast<const unsigned char *>(signing_input.data()), signing_input.size());
  expect(verified == 1, "ES256 signature verifies against the key");

  OPENSSL_free(der);
  ECDSA_SIG_free(sig);
}

} // namespace

int main() {
  testBase64Url();
  testHmac();
  testPemDetection();
  testJwtSignatureRoundTrip();

  if (failures > 0) {
    std::cerr << failures << " coinbase auth expectation(s) failed" << std::endl;
    return 1;
  }
  return 0;
}
