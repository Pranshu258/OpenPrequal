package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestNewFromEnvDefaults(t *testing.T) {
	// Clear relevant env vars
	os.Unsetenv("PROXY_URL")
	os.Unsetenv("BACKEND_PORT")
	os.Unsetenv("BACKEND_HOST")
	os.Unsetenv("BACKEND_URL")
	c := NewFromEnv()
	if c.ProxyURL != "http://localhost:8000" {
		t.Fatalf("unexpected ProxyURL default: %s", c.ProxyURL)
	}
	if c.BackendPort != "8001" {
		t.Fatalf("unexpected BackendPort default: %s", c.BackendPort)
	}
	if c.BackendURL == "" {
		t.Fatalf("expected BackendURL to be set")
	}
}

func TestSetupLoggingCreatesFile(t *testing.T) {
	dir := t.TempDir()
	lf := filepath.Join(dir, "openprequal_test.log")
	os.Setenv("LOG_FILE", lf)
	defer os.Unsetenv("LOG_FILE")
	if err := SetupLogging(); err != nil {
		t.Fatalf("SetupLogging failed: %v", err)
	}
	// file should exist (or be creatable)
	if _, err := os.Stat(lf); err != nil {
		t.Fatalf("expected log file to be created, stat failed: %v", err)
	}
}
