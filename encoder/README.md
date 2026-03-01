# encoder

A command-line tool for Base64 encoding/decoding and asymmetric key generation.

## Commands

| Command | Description |
|---------|-------------|
| `encode` | Base64-encode input |
| `decode` | Base64-decode input |
| `generatemaster` | Generate RSA 2048-bit asymmetric key pair |
| `generatekey` | Generate a new PEM-format private key (stdout) |

## Usage

```
encoder encode [input-file]
encoder decode [input-file]
encoder generatemaster
encoder generatekey
```

- For `encode` and `decode`: if an input file is specified, the tool reads from that file; otherwise input is read from stdin. Output is written to stdout.
- For `generatemaster`: generates `master_private.pem` and `master_public.pem` in the current directory. Uses the current time in milliseconds as the randomness seed for key generation.
- For `generatekey`: outputs a new PEM-format RSA private key to stdout. Each call produces a different key.

## Build

```bash
go build -o encoder ./cmd/encoder
```

On Windows:

```bash
go build -o encoder.exe ./cmd/encoder
```

## Examples

Encode from stdin:

```bash
echo "hello" | encoder encode
# aGVsbG8K
```

Decode from stdin:

```bash
echo "aGVsbG8K" | encoder decode
# hello
```

Encode a file:

```bash
encoder encode secrets.txt
```

Decode a file:

```bash
encoder decode encoded.txt
```

Pipe encode and decode:

```bash
echo "data" | encoder encode | encoder decode
```

Generate asymmetric key pair:

```bash
encoder generatemaster
# Creates master_private.pem and master_public.pem (RSA 2048-bit)
```

Generate a one-off private key (different each time):

```bash
encoder generatekey > mykey.pem
```
