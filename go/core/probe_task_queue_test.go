package core

import "testing"

func TestProbeTaskQueue(t *testing.T) {
	q := NewProbeTaskQueue()
	q.AddTask("b1")
	if q.Size() != 1 {
		t.Fatalf("expected size 1")
	}
	id := q.GetTask()
	if id == nil || *id != "b1" {
		t.Fatalf("expected b1")
	}
}
