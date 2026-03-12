package crypto

import (
	"bytes"
	"strings"
	"testing"
)

func TestEncryptDecryptRoundTrip(t *testing.T) {
	pepper := "test-pepper"
	cases := []struct {
		plaintext string
		password  string
	}{
		{"hello world", "password123"},
		{"", "empty-plaintext"},
		{"special chars: !@#$%^&*()", "pass"},
		{strings.Repeat("x", 10000), "long-plaintext"},
	}
	for _, tc := range cases {
		enc, err := Encrypt(tc.plaintext, tc.password, pepper)
		if err != nil {
			t.Fatalf("Encrypt(%q) error: %v", tc.plaintext, err)
		}
		got, err := Decrypt(enc, tc.password, pepper)
		if err != nil {
			t.Fatalf("Decrypt error: %v", err)
		}
		if got != tc.plaintext {
			t.Errorf("round-trip mismatch: got %q, want %q", got, tc.plaintext)
		}
	}
}

func TestEncryptIsDeterministic(t *testing.T) {
	// Same inputs must produce same output (fixed nonce from seed).
	pepper := "pepper"
	a, _ := Encrypt("test", "pass", pepper)
	b, _ := Encrypt("test", "pass", pepper)
	if a != b {
		t.Errorf("Encrypt is not deterministic: %q != %q", a, b)
	}
}

func TestDecryptWrongPassword(t *testing.T) {
	enc, _ := Encrypt("secret", "correct", "pepper")
	_, err := Decrypt(enc, "wrong", "pepper")
	if err == nil {
		t.Error("expected error for wrong password, got nil")
	}
}

func TestEncodedPasswordDeterministic(t *testing.T) {
	pepper := "pepper"
	a := EncodedPassword("mypassword", pepper)
	b := EncodedPassword("mypassword", pepper)
	if a != b {
		t.Errorf("EncodedPassword is not deterministic: %q != %q", a, b)
	}
	if a == "mypassword" {
		t.Error("EncodedPassword returned the original password unchanged")
	}
}

func TestRSAHybridRoundTrip(t *testing.T) {
	privPEM, pubPEM, err := GenerateRSAKeyPair()
	if err != nil {
		t.Fatalf("GenerateRSAKeyPair: %v", err)
	}
	plaintext := []byte("sensitive information that needs protecting")
	ct, err := EncryptWithPublicKeyHybrid([]byte(pubPEM), plaintext)
	if err != nil {
		t.Fatalf("EncryptWithPublicKeyHybrid: %v", err)
	}
	got, err := DecryptWithPrivateKeyHybrid([]byte(privPEM), ct)
	if err != nil {
		t.Fatalf("DecryptWithPrivateKeyHybrid: %v", err)
	}
	if !bytes.Equal(got, plaintext) {
		t.Errorf("RSA round-trip mismatch: got %q, want %q", got, plaintext)
	}
}

func TestRSAHybridDifferentCiphertexts(t *testing.T) {
	// Each call uses a fresh random AES key + nonce, so ciphertexts differ.
	_, pubPEM, _ := GenerateRSAKeyPair()
	ct1, _ := EncryptWithPublicKeyHybrid([]byte(pubPEM), []byte("data"))
	ct2, _ := EncryptWithPublicKeyHybrid([]byte(pubPEM), []byte("data"))
	if bytes.Equal(ct1, ct2) {
		t.Error("RSA hybrid encryption produced identical ciphertexts for same plaintext")
	}
}

func TestSeedLength(t *testing.T) {
	if len(staticSeed) < 28 {
		t.Errorf("seed.txt too short: need at least 28 bytes, got %d", len(staticSeed))
	}
}
