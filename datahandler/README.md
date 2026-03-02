# datahandler

A command-line tool for master key management and sensitive data records. Uses RSA hybrid encryption for record details, with master and trusted keys stored in a PostgreSQL database.

## Requirements

- PostgreSQL database
- `.env` file with:
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
  - `APP_SECRET_PEPPER` (secret used for key derivation)

## Commands

| Command | Description |
|---------|-------------|
| `generatemasterkey` | Generate RSA 2048-bit key pair, clear existing keys, create trusted key for master |
| `generatekey` | Generate a trusted key for a user password |
| `deletetrustedkey` | Delete a trusted key (cannot delete master) |
| `getrecordcount` | Return count of sensitive_data records |
| `getrecord` | Get single record by id, decrypt with user's private key |
| `getrecords` | Get all records, decrypt with user's private key |
| `createrecord` | Create record; reads base64-encoded JSON from stdin |
| `updaterecord` | Update record by id; reads base64-encoded JSON from stdin |
| `deleterecord` | Delete record by id (requires master password) |
| `test` | Run datahandler test |

## Usage

```
datahandler generatemasterkey [masterpassword]
datahandler generatekey [masterpassword] [userpassword]
datahandler deletetrustedkey [userpassword] [masterpassword]
datahandler getrecordcount
datahandler getrecord [id] [password]
datahandler getrecords [password]
datahandler createrecord [masterpassword]     (reads base64 JSON from stdin)
datahandler updaterecord [id] [masterpassword] (reads base64 JSON from stdin)
datahandler deleterecord [id] [masterpassword]
datahandler test
```

## Build

From the datahandler directory:

```bash
go build -o datahandler ./cmd
```

On Windows:

```bash
go build -o datahandler.exe ./cmd
```

## Examples

Generate master key pair (run once to set up):

```bash
datahandler generatemasterkey mymasterpassword
```

Generate a trusted key for a user:

```bash
datahandler generatekey mymasterpassword userpassword123
```

Create a record (JSON must be base64-encoded):

```bash
echo -n 'eyJkZXNjcmlwdGlvbiI6InRlc3QiLCJkZXRhaWxzIjoiY29udGVudCIsImlzX3ByaXZhdGUiOnRydWUsImlzX3NlbnNpdGl2ZSI6dHJ1ZX0=' | base64 -d
# Verify JSON: {"description":"test","details":"content","is_private":true,"is_sensitive":true}
echo 'eyJkZXNjcmlwdGlvbiI6InRlc3QiLCJkZXRhaWxzIjoiY29udGVudCIsImlzX3ByaXZhdGUiOnRydWUsImlzX3NlbnNpdGl2ZSI6dHJ1ZX0=' | datahandler createrecord mymasterpassword
```

Get record count:

```bash
datahandler getrecordcount
```

Get all records (decrypted with user's key):

```bash
datahandler getrecords userpassword123
```
