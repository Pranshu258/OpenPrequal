package core

import "sync"

type ProbeTaskQueue struct {
	mu    sync.Mutex
	set   map[string]struct{}
	queue []string
}

func NewProbeTaskQueue() *ProbeTaskQueue {
	return &ProbeTaskQueue{set: make(map[string]struct{}), queue: make([]string, 0)}
}

func (q *ProbeTaskQueue) Size() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.set)
}

func (q *ProbeTaskQueue) AddTask(id string) {
	q.mu.Lock()
	defer q.mu.Unlock()
	if _, ok := q.set[id]; !ok {
		q.set[id] = struct{}{}
		q.queue = append(q.queue, id)
	}
}

func (q *ProbeTaskQueue) GetTask() *string {
	q.mu.Lock()
	defer q.mu.Unlock()
	if len(q.queue) == 0 {
		return nil
	}
	id := q.queue[0]
	q.queue = q.queue[1:]
	delete(q.set, id)
	return &id
}
