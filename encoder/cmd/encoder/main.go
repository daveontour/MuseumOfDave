package main

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	_ "embed"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	mathrand "math/rand"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
	"golang.org/x/crypto/argon2"
)

var (
	dbPool     *pgxpool.Pool
	dbPoolErr  error
	dbPoolOnce sync.Once
)

// getDBPool returns a shared database connection pool. Initialization happens once.
func getDBPool() (*pgxpool.Pool, error) {
	dbPoolOnce.Do(func() {
		if err := godotenv.Load(".env"); err != nil {
			if exe, err := os.Executable(); err == nil {
				encoderDir := filepath.Dir(filepath.Dir(exe))
				_ = godotenv.Load(filepath.Join(encoderDir, ".env"))
			}
		}
		host := os.Getenv("DB_HOST")
		port := os.Getenv("DB_PORT")
		if port == "" {
			port = "5432"
		}
		name := os.Getenv("DB_NAME")
		user := os.Getenv("DB_USER")
		password := os.Getenv("DB_PASSWORD")
		if host == "" || name == "" || user == "" || password == "" {
			dbPoolErr = fmt.Errorf("missing DB config: set DB_HOST, DB_NAME, DB_USER, DB_PASSWORD in .env")
			return
		}
		connStr := fmt.Sprintf("postgres://%s:%s@%s:%s/%s", user, password, host, port, name)
		pool, err := pgxpool.New(context.Background(), connStr)
		if err != nil {
			dbPoolErr = fmt.Errorf("connect: %w", err)
			return
		}
		if err := pool.Ping(context.Background()); err != nil {
			pool.Close()
			dbPoolErr = fmt.Errorf("ping: %w", err)
			return
		}
		dbPool = pool
	})
	return dbPool, dbPoolErr
}

// 1. Embed a static seed from a file at compile time
// Create a file named 'seed.txt' with at least 32 random characters.
//
//go:embed seed.txt
var staticSeed []byte

type timeSeededReader struct {
	rng *mathrand.Rand
}

func (r *timeSeededReader) Read(p []byte) (n int, err error) {
	for i := range p {
		p[i] = byte(r.rng.Intn(256))
	}
	return len(p), nil
}

// getPepper retrieves the secret key from the OS environment
func getPepper() string {
	pepper := os.Getenv("APP_SECRET_PEPPER")
	if pepper == "" {
		// In production, you should probably exit if this is missing
		return "default-fallback-not-secure-2026"
	}
	return pepper
}

// deriveDeterministicKey combines password, seed, and pepper
func deriveDeterministicKey(password string) []byte {
	pepper := getPepper()
	// We combine the password and pepper to create a high-entropy input
	combinedInput := []byte(password + pepper)

	// Use the first 16 bytes of our embedded seed as the Salt
	salt := staticSeed[:16]

	// Argon2id: 1 iteration, 64MB memory, 4 threads, 32-byte output
	return argon2.IDKey(combinedInput, salt, 1, 64*1024, 4, 32)
}

func encrypt(plainText string, password string) (string, error) {
	key := deriveDeterministicKey(password)

	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}

	// Use bytes 16-28 of the seed as a fixed 12-byte Nonce
	nonce := staticSeed[16:28]

	cipherText := gcm.Seal(nil, nonce, []byte(plainText), nil)
	return base64.StdEncoding.EncodeToString(cipherText), nil
}

func decrypt(cryptoText string, password string) (string, error) {
	data, err := base64.StdEncoding.DecodeString(cryptoText)
	if err != nil {
		return "", err
	}

	key := deriveDeterministicKey(password)

	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}

	nonce := staticSeed[16:28]

	// Decrypt and verify integrity
	plainText, err := gcm.Open(nil, nonce, data, nil)
	if err != nil {
		return "", errors.New("decryption failed: wrong password or tampered data")
	}

	return string(plainText), nil
}
func getEncodedPassword(password string) string {
	password, _ = encrypt(password, password)
	password, _ = encrypt(password, string(staticSeed[:16]))
	password, _ = encrypt(password, password)
	return password
}
func readMasterKeysFromDB() (string, error) {
	pool, err := getDBPool()
	if err != nil {
		return "", err
	}
	var privateKeyPEM string
	err = pool.QueryRow(context.Background(),
		`SELECT public_key FROM master_keys LIMIT 1`).
		Scan(&privateKeyPEM)
	if err != nil {
		return "", fmt.Errorf("query master_keys: %w", err)
	}
	return privateKeyPEM, nil
}

// writeMasterKeysToDB inserts the key pair into the master_keys table.
func writeMasterKeysToDB(publicKeyPEM string) error {
	pool, err := getDBPool()
	if err != nil {
		return err
	}
	_, err = pool.Exec(context.Background(), `TRUNCATE TABLE master_keys`)
	if err != nil {
		return fmt.Errorf("truncate: %w", err)
	}
	_, err = pool.Exec(context.Background(), `TRUNCATE TABLE trusted_keys`)
	if err != nil {
		return fmt.Errorf("truncate: %w", err)
	}
	_, err = pool.Exec(context.Background(), `TRUNCATE TABLE sensitive_data`)
	if err != nil {
		return fmt.Errorf("truncate: %w", err)
	}
	_, err = pool.Exec(context.Background(),
		`INSERT INTO master_keys (comment,  public_key) VALUES ($1, $2)`,
		"Generated by encoder", publicKeyPEM)
	if err != nil {
		return fmt.Errorf("insert: %w", err)
	}
	return nil
}

// GetMasterPrivateKey retrieves and decrypts the master private key from the
// database using the same string that was passed to generatemaster.
func GetMasterPrivateKey(password string) (string, error) {
	key, err := getPrivateKeyFromDB(password, true)
	if err != nil || key == "" {
		return "", fmt.Errorf("Could not get master private key: %w", err)
	}
	return key, nil
}

// GetMasterPublicKey retrieves and decrypts the master public key from the
// database using the same string that was passed to generatemaster.
func GetMasterPublicKey(password string) (string, error) {

	// encoderPassword := getEncodedPassword(password)

	encryptedPublic, err := readMasterKeysFromDB()
	if err != nil {
		return "", fmt.Errorf("read master keys: %w", err)
	}

	publicKeyPEM, err := decrypt(encryptedPublic, password)
	if err != nil {
		return "", fmt.Errorf("decrypt public key: %w", err)
	}
	return publicKeyPEM, nil
}

func generateTrustedKeys(userpassword string, masterpassword string, mKey string) {

	//Uses the master password to get the master private key
	//which is then encrypted with the user password
	//and then saved to the database

	//No other user information is saved in the database
	is_master := masterpassword == userpassword
	var masterPrivateKey string
	var err error
	if mKey == "" {
		masterPrivateKey, err = GetMasterPrivateKey(masterpassword)
		if err != nil {
			fmt.Fprintf(os.Stderr, "generateTrustedKeys: %v\n", err)
			os.Exit(1)
		}
	} else {
		masterPrivateKey = mKey
	}
	//Encrypt the master public key with the encrypted form of the user password
	encryptedUserKey, err := encrypt(masterPrivateKey, getEncodedPassword(userpassword))
	if err != nil {
		fmt.Fprintf(os.Stderr, "generateTrustedKeys Failed to encrypt master private key: %v\n", err)
		os.Exit(1)
	}

	pool, err := getDBPool()
	if err != nil {
		fmt.Fprintf(os.Stderr, "generateTrustedKeys Failed to get database pool: %v\n", err)
		os.Exit(1)
	}
	_, err = pool.Exec(context.Background(), `INSERT INTO trusted_keys (key, is_master) VALUES ($1, $2)`, encryptedUserKey, is_master)
	if err != nil {
		fmt.Fprintf(os.Stderr, "generateTrustedKeys Failed to insert trusted key into database: %v\n", err)
		os.Exit(1)
	}
}

func EncryptWithPublicKey(publicKeyPEM []byte, plaintext []byte) ([]byte, error) {
	block, _ := pem.Decode(publicKeyPEM)
	if block == nil {
		return nil, fmt.Errorf("failed to decode PEM block")
	}
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("parse public key: %w", err)
	}
	rsaPub, ok := pub.(*rsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("not an RSA public key")
	}
	hash := sha256.New()
	return rsa.EncryptOAEP(hash, rand.Reader, rsaPub, plaintext, nil)
}

// EncryptWithPublicKeyHybrid encrypts plaintext of any length using hybrid encryption:
// a random AES-256 key encrypts the data; the key is encrypted with the RSA public key.
// Format: [RSA-encrypted key][AES-GCM nonce][AES-GCM ciphertext]
func EncryptWithPublicKeyHybrid(publicKeyPEM []byte, plaintext []byte) ([]byte, error) {
	rsaPub, err := parseRSAPublicKey(publicKeyPEM)
	if err != nil {
		return nil, err
	}
	// 1. Generate random 32-byte AES key
	aesKey := make([]byte, 32)
	if _, err := io.ReadFull(rand.Reader, aesKey); err != nil {
		return nil, err
	}
	// 2. Encrypt AES key with RSA
	hash := sha256.New()
	encryptedKey, err := rsa.EncryptOAEP(hash, rand.Reader, rsaPub, aesKey, nil)
	if err != nil {
		return nil, err
	}
	// 3. Encrypt plaintext with AES-GCM
	block, err := aes.NewCipher(aesKey)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, err
	}
	ciphertext := gcm.Seal(nil, nonce, plaintext, nil)
	// 4. Pack: encrypted_key || nonce || ciphertext
	return append(append(encryptedKey, nonce...), ciphertext...), nil
}

// DecryptWithPrivateKeyHybrid decrypts data produced by EncryptWithPublicKeyHybrid.
func DecryptWithPrivateKeyHybrid(privateKeyPEM []byte, data []byte) ([]byte, error) {
	priv, err := parseRSAPrivateKey(privateKeyPEM)
	if err != nil {
		return nil, err
	}
	// RSA-encrypted key is 256 bytes for 2048-bit RSA; nonce is 12 for GCM
	const rsaEncryptedLen = 256
	const gcmNonceLen = 12
	if len(data) < rsaEncryptedLen+gcmNonceLen {
		return nil, fmt.Errorf("ciphertext too short")
	}
	encryptedKey := data[:rsaEncryptedLen]
	nonce := data[rsaEncryptedLen : rsaEncryptedLen+gcmNonceLen]
	ciphertext := data[rsaEncryptedLen+gcmNonceLen:]
	// 1. Decrypt AES key with RSA
	hash := sha256.New()
	aesKey, err := rsa.DecryptOAEP(hash, rand.Reader, priv, encryptedKey, nil)
	if err != nil {
		return nil, err
	}
	// 2. Decrypt with AES-GCM
	block, err := aes.NewCipher(aesKey)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	return gcm.Open(nil, nonce, ciphertext, nil)
}

func parseRSAPublicKey(publicKeyPEM []byte) (*rsa.PublicKey, error) {
	block, _ := pem.Decode(publicKeyPEM)
	if block == nil {
		return nil, fmt.Errorf("failed to decode PEM block")
	}
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("parse public key: %w", err)
	}
	rsaPub, ok := pub.(*rsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("not an RSA public key")
	}
	return rsaPub, nil
}

func parseRSAPrivateKey(privateKeyPEM []byte) (*rsa.PrivateKey, error) {
	block, _ := pem.Decode(privateKeyPEM)
	if block == nil {
		return nil, fmt.Errorf("failed to decode PEM block")
	}
	return x509.ParsePKCS1PrivateKey(block.Bytes)
}
func DecryptCipherText(privateKeyPEM []byte, ciphertext []byte) ([]byte, error) {
	block, _ := pem.Decode(privateKeyPEM)
	if block == nil {
		return nil, fmt.Errorf("failed to decode PEM block")
	}
	priv, err := x509.ParsePKCS1PrivateKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("parse private key: %w", err)
	}
	hash := sha256.New()
	plaintext, err := rsa.DecryptOAEP(hash, rand.Reader, priv, ciphertext, nil)
	if err != nil {
		return nil, fmt.Errorf("decrypt: %w", err)
	}
	return plaintext, nil
}

func getPrivateKeyFromDB(userpassword string, noReport bool) (string, error) {

	if !noReport {
		fmt.Fprintf(os.Stderr, "Getting private key from database for password with user password: %s\n", userpassword)
	}

	pool, err := getDBPool()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get database pool: %v\n", err)
		return "", nil
	}

	//select all the encrypted user keys from the database

	rows, err := pool.Query(context.Background(), `SELECT key FROM trusted_keys`)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to select trusted keys: %v\n", err)
		return "", err
	}
	defer rows.Close()

	for rows.Next() {
		var encryptedUserKey string
		_ = rows.Scan(&encryptedUserKey)

		decryptedUserKey, err := decrypt(encryptedUserKey, getEncodedPassword(userpassword))
		if err != nil {
			continue
		} else {
			if !noReport {
				fmt.Printf("Found  trusted key for password: %s \n", userpassword)
				fmt.Printf("Trusted key: %s \n", decryptedUserKey)
			}
			return decryptedUserKey, nil
		}
	}

	return "", nil

}

func getTrustedKeyID(userpassword string) (int, error) {
	pool, err := getDBPool()
	if err != nil {
		return 0, fmt.Errorf("unable to get database pool: %v", err)
	}
	rows, err := pool.Query(context.Background(), `SELECT key, id FROM trusted_keys`)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to select trusted keys: %v\n", err)
		return -1, err
	}
	defer rows.Close()

	for rows.Next() {
		var encryptedUserKey string
		var id int
		_ = rows.Scan(&encryptedUserKey, &id)

		_, err := decrypt(encryptedUserKey, getEncodedPassword(userpassword))
		if err != nil {
			continue
		} else {
			return id, nil
		}
	}
	return -1, fmt.Errorf("no trusted key found for password: %v", userpassword)
}

func checkMasterPassword(password string) bool {
	pool, err := getDBPool()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get database pool: %v\n", err)
		os.Exit(1)
	}
	rows, err := pool.Query(context.Background(), `SELECT key FROM trusted_keys WHERE is_master = true`)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get master public key: %v\n", err)
		os.Exit(1)
	}
	defer rows.Close()
	for rows.Next() {
		var key string
		err = rows.Scan(&key)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Unable to scan master public key: %v\n", err)
			os.Exit(1)
		}
		_, err := decrypt(key, password)
		if err != nil {
			return false
		} else {
			return true
		}
	}
	return false
}

const helpSummary = `encoder - Master key management and sensitive data records

Usage:
  encoder generatemasterkey [masterpassword]
  encoder generatekey  [userpassword] [masterpassword]
  encoder deletetrustedkey [userpassword] [masterpassword]
  encoder getrecordcount
  encoder getrecord [id] [password]
  encoder getrecords [password]
  encoder createrecord [masterpassword]     (reads base64 JSON from stdin)
  encoder updaterecord [id] [masterpassword] (reads base64 JSON from stdin)
  encoder deleterecord [id] [masterpassword]
  encoder test

Commands:
  generatemasterkey   Generate RSA 2048-bit key pair, clear existing keys, create trusted key for master.
  generatekey         Generate a trusted key for the user password.
  deletetrustedkey    Delete a trusted key (cannot delete master password).
  getrecordcount      Return count of sensitive_data records.
  getrecord           Get single record by id, decrypt with user's private key.
  getrecords          Get all records, decrypt with user's private key.
  createrecord        Create record; reads base64-encoded JSON from stdin.
  updaterecord        Update record by id; reads base64-encoded JSON from stdin.
  deleterecord        Delete record by id (requires master password).
  test                Run encoder test.
`

func main() {
	if len(os.Args) < 2 {
		fmt.Fprint(os.Stderr, helpSummary)
		os.Exit(1)
	}

	cmd := os.Args[1]
	args := os.Args[2:]

	switch cmd {
	case "test":
		testEncoder()
		os.Exit(0)
	case "generatemasterkey":
		generateMasterKey(args)
		fmt.Fprintf(os.Stdout, "Master key pair generated and trusted key inserted into database\n")
		os.Exit(0)
	case "generatekey":
		generateTrustedKeys(args[0], args[1], "")
		fmt.Fprintf(os.Stdout, "Trusted key generated and inserted into database\n")
		os.Exit(0)
	case "deletetrustedkey":
		deleteTrustedKey(args)
		fmt.Fprintf(os.Stdout, "Trusted key deleted from database\n")
		os.Exit(0)
	case "getrecordcount":
		count := getRecordCount()
		fmt.Fprintf(os.Stdout, "{ \"count\": %d }", count)
		os.Exit(0)
	case "getrecord":
		getRecord(args)
		os.Exit(0)
	case "getrecords":
		getRecords(args)
		os.Exit(0)
	case "createrecord":
		createRecord(args[0], "")
		fmt.Fprintf(os.Stdout, "Record created in the database\n")
		os.Exit(0)
	case "updaterecord":
		createRecord(args[1], args[0])
		fmt.Fprintf(os.Stdout, "Record updated in the database\n")
		os.Exit(0)
	case "deleterecord":
		deleteRecord(args)
		fmt.Fprintf(os.Stdout, "Record deleted from the database\n")
		os.Exit(0)
	case "-h", "--help", "help":
		fmt.Print(helpSummary)
		os.Exit(0)
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n\n", cmd)
		fmt.Fprint(os.Stderr, helpSummary)
		os.Exit(1)
	}

}
func testEncoder() {
	// Set the environment variable (In a real app, do this in your shell/docker)
	fmt.Fprintf(os.Stderr, "Test encoder\n")
	fmt.Fprintf(os.Stdin, "Test encoder\n")
	os.Exit(0)
}

func generateMasterKey(args []string) {
	// Use milliseconds of current time for randomness as requested
	seed := time.Now().UnixMilli()
	rng := mathrand.New(mathrand.NewSource(seed))

	// RSA 2048-bit keys (meets "at least 1024 bit" requirement)
	priv, err := rsa.GenerateKey(&timeSeededReader{rng: rng}, 2048)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Generating master key pair failed: %v\n", err)
		os.Exit(1)
	}

	privPEM := pem.EncodeToMemory(&pem.Block{
		Type:  "RSA PRIVATE KEY",
		Bytes: x509.MarshalPKCS1PrivateKey(priv),
	})
	pubPKIX, err := x509.MarshalPKIXPublicKey(&priv.PublicKey)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Generating master key pair failed: %v\n", err)
		os.Exit(1)
	}
	pubPEM := pem.EncodeToMemory(&pem.Block{
		Type:  "PUBLIC KEY",
		Bytes: pubPKIX,
	})

	password := args[0]

	privateKeyPEM := string(privPEM)
	publicKeyPEM := string(pubPEM)

	publicKeyPEM, err = encrypt(publicKeyPEM, password)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to encrypt master public key: %v\n", err)
		os.Exit(1)
	}

	if err := writeMasterKeysToDB(publicKeyPEM); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write master key pair to database: %v\n", err)
		os.Exit(1)
	}

	//So the private kay is available to the owner..
	generateTrustedKeys(password, password, privateKeyPEM)
	fmt.Fprintf(os.Stderr, "Master key pair generated and trusted key inserted into database\n")

}

func deleteTrustedKey(args []string) {
	password := args[0]
	masterpassword := args[1]

	if password == masterpassword {
		fmt.Fprintf(os.Stderr, "Cannot delete master password:\n")
		os.Exit(1)
	}

	if !checkMasterPassword(masterpassword) {
		fmt.Fprintf(os.Stderr, "Invalid master password:\n")
		os.Exit(1)
	}
	id, err := getTrustedKeyID(password)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get trusted key ID: %v\n", err)
		os.Exit(1)
	}
	pool, err := getDBPool()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get database pool: %v\n", err)
		os.Exit(1)
	}
	_, err = pool.Exec(context.Background(), `DELETE FROM trusted_keys WHERE id = $1`, id)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to delete trusted key from database: %v\n", err)
		os.Exit(1)
	}
	fmt.Fprintf(os.Stdout, "Trusted key deleted from the database\n")
	os.Exit(0)
}
func deleteRecord(args []string) {

	masterpassword := args[1]
	id := args[0]

	pool, err := getDBPool()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get database pool: %v\n", err)
		os.Exit(1)
	}

	if checkMasterPassword(masterpassword) {
		_, err = pool.Exec(context.Background(), `DELETE FROM sensitive_data WHERE id = $1`, id)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Failed to delete record from database: %v\n", err)
			os.Exit(1)
		}
		fmt.Fprintf(os.Stdout, "Record deleted from the database\n")
		os.Exit(0)
	} else {
		fmt.Fprintf(os.Stderr, "Invalid master password: %v\n", err)
		os.Exit(1)
	}
}

func getRecord(args []string) {
	password := args[1]
	id := args[0]

	privateKey, err := getPrivateKeyFromDB(password, true)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get private key: %v\n", err)
		os.Exit(1)
	}

	if privateKey == "" {
		fmt.Fprintf(os.Stderr, "Private key is empty, returning empty record\n")
		fmt.Fprintf(os.Stdin, "[]")
		os.Exit(0)
	}

	pool, err := getDBPool()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get database pool: %v\n", err)
		os.Exit(1)
	}
	rows, err := pool.Query(context.Background(), `SELECT * FROM sensitive_data WHERE id = $1`, id)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get records: %v\n", err)
		os.Exit(1)
	}
	defer rows.Close()
	records := []map[string]interface{}{}
	for rows.Next() {
		var id int
		var description, details string
		var isPrivate, isSensitive bool
		var createdAt, updatedAt interface{}
		err = rows.Scan(&id, &description, &details, &isPrivate, &isSensitive, &createdAt, &updatedAt)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Unable to scan record: %v\n", err)
			os.Exit(1)
		}
		if privateKey != "" {
			//base64 decode the details
			detailsBytes, err := base64.StdEncoding.DecodeString(details)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Unable to decode details: %v\n", err)
				os.Exit(1)
			}
			//	decryptedBytes, err := DecryptWithPrivateKeyHybrid([]byte(pkey), []byte(details))
			decryptedBytes, err := DecryptWithPrivateKeyHybrid([]byte(privateKey), detailsBytes)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Unable to decrypt details: %v\n", err)
				os.Exit(1)
			}
			details = string(decryptedBytes)
		} else {
			details = "*****************"
			description = "*****************"
		}

		record := map[string]interface{}{
			"id":           id,
			"description":  description,
			"details":      details,
			"is_private":   isPrivate,
			"is_sensitive": isSensitive,
			"created_at":   createdAt,
			"updated_at":   updatedAt,
		}
		records = append(records, record)
	}
	if err := rows.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "Unable to iterate rows: %v\n", err)
		os.Exit(1)
	}
	//format the records into JSON and output to stdout
	jsonData, err := json.Marshal(records)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to marshal records: %v\n", err)
		os.Exit(1)
	}
	fmt.Fprintf(os.Stdout, "%s\n", string(jsonData))
	os.Exit(0)
}

func createRecord(masterpassword string, id string) {

	// A non-empty id means we are updating a record
	update := id != ""

	inputBytes, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read input from stdin: %v\n", err)
		os.Exit(1)
	}
	recordData, err := base64.StdEncoding.DecodeString(string(inputBytes))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to decode base64 input: %v\n", err)
		os.Exit(1)
	}
	fmt.Fprintf(os.Stderr, "Record data: %s\n", string(recordData))
	var jsonData map[string]interface{}
	if err := json.Unmarshal(recordData, &jsonData); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to unmarshal record data: %v\n", err)
		os.Exit(1)
	}
	_ = jsonData
	// get the description, details, is_private and is_sensitive from the jsonData
	description := jsonData["description"].(string)
	details := jsonData["details"].(string)
	is_private := jsonData["is_private"].(bool)
	is_sensitive := jsonData["is_sensitive"].(bool)
	// get the master public key and encrypt the details using the public key
	masterPublicKey, err := GetMasterPublicKey(masterpassword)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to get master public key: %v\n", err)
		os.Exit(1)
	}
	encryptedDetailsBytes, err := EncryptWithPublicKeyHybrid([]byte(masterPublicKey), []byte(details))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to encrypt details: %v\n", err)
		os.Exit(1)
	}
	encryptedDetails := base64.StdEncoding.EncodeToString(encryptedDetailsBytes)
	// insert the record into the database
	pool, err := getDBPool()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get database pool: %v\n", err)
		os.Exit(1)
	}
	_, err = pool.Exec(context.Background(), `INSERT INTO sensitive_data (description, details, is_private, is_sensitive) VALUES ($1, $2, $3, $4)`, description, encryptedDetails, is_private, is_sensitive)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert record into database: %v\n", err)
		os.Exit(1)
	}
	if update {
		//Delete the old record from the database
		_, err = pool.Exec(context.Background(), `DEELTE from sensitive_data  WHERE id = $1`, id)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Failed to update record in database: %v\n", err)
			os.Exit(1)
		}
		fmt.Fprintf(os.Stdout, "Record updated in the database\n")
		os.Exit(0)
	} else {
		fmt.Fprintf(os.Stdout, "Record created in the database\n")
		os.Exit(0)
	}

}

func getRecordCount() int {
	//Connec to the database and get the count of records in the sensitive_data table
	pool, err := getDBPool()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get database pool: %v\n", err)
		os.Exit(1)
	}
	rows, err := pool.Query(context.Background(), `SELECT COUNT(*) FROM sensitive_data`)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get record count: %v\n", err)
		os.Exit(1)
	}
	var count int
	count = 0
	defer rows.Close()
	for rows.Next() {
		err = rows.Scan(&count)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Unable to scan record count: %v\n", err)
			os.Exit(1)
		}
		fmt.Fprintf(os.Stdout, "Record count: %d\n", count)
	}
	if err := rows.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "Unable to iterate rows: %v\n", err)
		os.Exit(1)
	}
	return count
}

func getRecords(args []string) {

	password := args[0]
	_ = password

	privateKey, err := getPrivateKeyFromDB(password, true)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get private key: %v\n", err)
		os.Exit(1)
	}

	pool, err := getDBPool()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get database pool: %v\n", err)
		os.Exit(1)
	}
	rows, err := pool.Query(context.Background(), `SELECT * FROM sensitive_data`)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to get records: %v\n", err)
		os.Exit(1)
	}
	defer rows.Close()
	records := []map[string]interface{}{}
	for rows.Next() {
		var id int
		var description, details string
		var isPrivate, isSensitive bool
		var createdAt, updatedAt interface{}
		err = rows.Scan(&id, &description, &details, &isPrivate, &isSensitive, &createdAt, &updatedAt)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Unable to scan record: %v\n", err)
			os.Exit(1)
		}
		if privateKey != "" {
			//privateKey, _ = decrypt(privateKey, password)
			fmt.Fprintf(os.Stderr, "Private key: %s\n", privateKey)
			//base64 decode the details
			detailsBytes, err := base64.StdEncoding.DecodeString(details)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Unable to decode details: %v\n", err)
				os.Exit(1)
			}
			//	decryptedBytes, err := DecryptWithPrivateKeyHybrid([]byte(pkey), []byte(details))
			decryptedBytes, err := DecryptWithPrivateKeyHybrid([]byte(privateKey), detailsBytes)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Unable to decrypt details: %v\n", err)
				os.Exit(1)
			}
			details = string(decryptedBytes)
		} else {
			details = "*****************"
		}

		record := map[string]interface{}{
			"id":           id,
			"description":  description,
			"details":      details,
			"is_private":   isPrivate,
			"is_sensitive": isSensitive,
			"created_at":   createdAt,
			"updated_at":   updatedAt,
		}
		records = append(records, record)
	}
	if err := rows.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "Unable to iterate rows: %v\n", err)
		os.Exit(1)
	}
	//format the records into JSON and output to stdout
	jsonData, err := json.Marshal(records)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to marshal records: %v\n", err)
		os.Exit(1)
	}
	fmt.Fprintf(os.Stdout, "%s\n", string(jsonData))
	os.Exit(0)
}
