package core

import "time"

// Simple profiler decorator analogs: provide helper functions. For now we keep them no-ops.
func ProfileSync(name string, fn func()) {
	start := time.Now()
	fn()
	_ = time.Since(start)
}
