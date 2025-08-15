import asyncio
import unittest

from core.probe_task_queue import ProbeTaskQueue


class TestProbeTaskQueue(unittest.IsolatedAsyncioTestCase):
    async def test_add_and_get_task(self):
        queue = ProbeTaskQueue()
        await queue.add_task("backend1")
        task = await queue.get_task()
        self.assertEqual(task, "backend1")
        queue.task_done()

    async def test_queue_order(self):
        queue = ProbeTaskQueue()
        await queue.add_task("a")
        await queue.add_task("b")
        t1 = await queue.get_task()
        t2 = await queue.get_task()
        self.assertEqual([t1, t2], ["a", "b"])
        queue.task_done()
        queue.task_done()


if __name__ == "__main__":
    unittest.main()
