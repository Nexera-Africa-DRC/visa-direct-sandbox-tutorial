# Debugging technique — decompile vdpplayground.jar

The Visa Developer Center Playground (`vdpplayground.jar`) is the official desktop GUI for testing Visa APIs. It implements the full handshake correctly — Basic Auth + mTLS + MLE + the right headers in the right order. When your own code mysteriously fails but the playground succeeds, decompiling the JAR gives you the exact reference implementation.

This is how I discovered **Pitfall 5** (A128GCM not A256GCM) and **Pitfall 6** (keyId HTTP header).

## Prerequisites

- The playground JAR: download from the Visa Developer dashboard (Assets section)
- Java 21 (or any Java 11+)
- [CFR](https://www.benf.org/other/cfr/), a Java decompiler that handles obfuscated code reasonably

## Step 1 — Grab CFR

```bash
curl -sL -o /tmp/cfr.jar \
  "https://github.com/leibnitz27/cfr/releases/download/0.152/cfr-0.152.jar"
```

## Step 2 — Extract embedded JARs

The playground is packaged as a "JAR in JAR" with Eclipse's `JarRsrcLoader`. The actual Visa code is inside `vdpplayground.jar` as nested JARs. Extract them:

```bash
cd ~/path/to/vdpplayground
mkdir -p lib
unzip -o -j vdpplayground.jar '*.jar' -d lib/
```

## Step 3 — Decompile

```bash
mkdir -p /tmp/vdp-decompiled
java -jar /tmp/cfr.jar vdpplayground.jar \
  --outputdir /tmp/vdp-decompiled \
  --caseinsensitivefs true
```

## Step 4 — Read the right files

The two files you want are:

- `/tmp/vdp-decompiled/com/visa/vdp/main/utils/EncryptionUtils.java` — MLE implementation (encrypt + decrypt)
- `/tmp/vdp-decompiled/com/visa/vdp/main/utils/VisaAPIClient.java` — HTTP client, specifically `doMutualAuthRequest` method

Grep for the key insights:

```bash
# How does Visa build the JWE header?
grep -n "JWEAlgorithm\|EncryptionMethod" \
  /tmp/vdp-decompiled/com/visa/vdp/main/utils/EncryptionUtils.java

# Which HTTP headers does Visa send on MLE requests?
grep -n "setHeader" \
  /tmp/vdp-decompiled/com/visa/vdp/main/utils/VisaAPIClient.java
```

Expected output (abbreviated):

```java
// EncryptionUtils.java
JWEHeader.Builder headerBuilder =
    new JWEHeader.Builder(JWEAlgorithm.RSA_OAEP_256, EncryptionMethod.A128GCM);
headerBuilder.keyID(this.keyID);
headerBuilder.customParam("iat", (Object)System.currentTimeMillis());

// VisaAPIClient.java (doMutualAuthRequest, abbreviated)
request.setHeader("Content-Type", "application/json");
request.setHeader("Accept", "application/json");
request.setHeader("Authorization",
    BasicAuthHeaderGenerator.getBasicAuthHeader(vdpUserId, vdpPwd));
if (isMLE) {
    request.setHeader("keyId", keyId);
    encrUtil = new EncryptionUtils(keyId, mlePrivateKey, mlePublicKey);
    payLoad = encrUtil.getEncryptedPayload(body);
}
```

That's where I learned:

- **Pitfall 5**: Visa uses `A128GCM`, not `A256GCM` — the default most JWE libraries pick.
- **Pitfall 6**: The HTTP header is literally `keyId: <same value as kid in the JWE>`, and it's only added when MLE is enabled.
- Bonus: `iat` is `System.currentTimeMillis()`, so **milliseconds since epoch**, not seconds.

## Running the playground on Java 21+

The 2019-vintage playground calls into `sun.security.util.DerInputStream`, which is encapsulated in modern JDKs. Open the JPMS modules:

```bash
cd ~/path/to/vdpplayground
CP="vdpplayground.jar"
for jar in lib/*.jar; do CP="$CP:$jar"; done

java \
  --add-opens java.base/sun.security.util=ALL-UNNAMED \
  --add-opens java.base/sun.security.rsa=ALL-UNNAMED \
  --add-opens java.base/sun.security.x509=ALL-UNNAMED \
  --add-opens java.base/sun.security.pkcs=ALL-UNNAMED \
  --add-opens java.base/sun.security.ssl=ALL-UNNAMED \
  --add-opens java.base/sun.security.provider=ALL-UNNAMED \
  --add-opens java.base/javax.crypto=ALL-UNNAMED \
  -cp "$CP" com.visa.vdp.main.playground.VDPlay
```

The Swing UI should pop up. Configure your credentials, flip MLE to ON, enter the push funds endpoint and body, hit Send — if it returns `actionCode: 00`, you have a confirmed-working reference you can compare against.

## When to use this technique

- Your code fails with a cryptic error that disappears when you use the playground. The decompiled source shows you what the playground does that you don't.
- The public docs don't specify a format detail (JWE algorithm, header casing, body serialization).
- You suspect your credentials or project state are OK but something in the request shape is wrong.

Decompiling is boring and sometimes tedious, but when the official docs stop helping, it's the best signal you can get.
