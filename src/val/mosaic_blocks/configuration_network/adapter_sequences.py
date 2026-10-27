"""Exercise the canonical-to-native adapter with independently computed images."""

import random
from pyuvm import uvm_sequence
from configuration_network.transaction import NetworkItem
from configuration_network.adapter_model import ShellModel
from configuration_network.layout import crc32c


class AdapterSequence(uvm_sequence):
    def __init__(self, c, active, coverage):
        super().__init__("tile_adapter_conformance")
        self.c, self.active, self.coverage = c, active, coverage
        self.shell = ShellModel(c.parameters)
        self.inputs = {n: 0 for n in c.widths if n.startswith("i_") and n != "i_clk"}
        self.number = 0
        self.rng = random.Random(c.seed)

    async def cycle(self, label="adapter", **ports):
        self.inputs.update(ports)
        item = NetworkItem(f"{label}_{self.number}", self.inputs | self.shell.drive())
        self.number += 1
        await self.start_item(item)
        await self.finish_item(item)
        self.shell.step(item.pre)
        return item

    async def send(self, command, **fields):
        defaults = dict(
            command=command,
            transaction_id=self.number % 256,
            sequence_id=self.number,
            epoch=0,
            owner_id=0,
            kernel_id=3,
            package_id=7,
            context_id=0,
            expected_version=0,
            word_index=0,
            write_data=0,
            write_strobe=(1 << (self.c.parameters["CONFIG_DATA_WIDTH"] // 8)) - 1,
            expected_crc=0,
            tag=self.number % 65536,
        )
        defaults.update(fields)
        self.inputs.update({"i_request_" + n: v for n, v in defaults.items()})
        for _ in range(200):
            item = await self.cycle("request", i_request_valid=1)
            if item.pre["o_request_ready"]:
                break
        else:
            raise AssertionError("Adapter request stuck")
        self.inputs["i_request_valid"] = 0

    async def wait(self):
        for _ in range(200):
            if self.active["records"]:
                return self.active["records"].pop(0)
            await self.cycle("response")
        raise AssertionError("Adapter response stuck")

    async def request(self, command, **fields):
        await self.send(command, **fields)
        return await self.wait()

    async def load(self, context=0, package=7, version=0):
        p = self.c.parameters
        words = [
            self.rng.getrandbits(p["CONFIG_DATA_WIDTH"])
            for _ in range(p["CONFIG_WORD_COUNT"])
        ]
        for wi, value in enumerate(words):
            response = await self.request(
                1,
                context_id=context,
                package_id=package,
                expected_version=version + wi,
                word_index=wi,
                write_data=value,
            )
            assert (
                response["status"] == 0
                and response["context_version"] == version + wi + 1
            )
            if wi == 0:
                before = len([r for r in self.shell.history if r["command"] == 0])
                rejected = await self.request(
                    1,
                    context_id=context,
                    package_id=package + 1,
                    expected_version=version + 1,
                    word_index=1,
                    write_data=123,
                )
                assert rejected["status"] == 1 and rejected["error_code"] == 24
                assert (
                    len([r for r in self.shell.history if r["command"] == 0]) == before
                )
                self.coverage.hit("loading_package_identity")

        version += len(words)
        image = crc32c(
            b"".join(w.to_bytes(p["CONFIG_DATA_WIDTH"] // 8, "little") for w in words)
        )
        response = await self.request(
            3,
            context_id=context,
            package_id=package,
            expected_version=version,
            expected_crc=image,
        )
        assert response["status"] == 0 and response["image_crc"] == image
        return words, version, image

    async def body(self):
        for _ in range(3):
            await self.cycle("reset")
        await self.cycle(
            "release_reset", i_reset_n=1, i_response_ready=1, i_commit_ack_ready=0
        )
        words, version, image = await self.load()
        for wi, value in enumerate(words):
            response = await self.request(2, word_index=wi)
            assert response["status"] == 0 and response["read_data"] == value
        self.coverage.hit("write_read_validate")
        for fields, error in (
            (dict(expected_version=version - 1), 9),
            (dict(owner_id=1), 5),
            (dict(context_id=255), 8),
            (dict(word_index=65535), 7),
        ):
            before = len([r for r in self.shell.history if r["command"] == 0])
            response = await self.request(1, **fields)
            assert response["status"] == 1 and response["error_code"] == error, response
            assert len([r for r in self.shell.history if r["command"] == 0]) == before
        self.coverage.hit("preflight_version")
        response = await self.request(6, expected_version=version, expected_crc=image)
        assert response["status"] == 0 and response["prepared"]
        assert self.shell.active is None
        assert not any(r["command"] == 3 for r in self.shell.history)
        self.coverage.hit("prepare_no_activation")
        await self.send(5)
        await self.cycle("backpressure", i_response_ready=0)
        for _ in range(20):
            await self.cycle("backpressure_hold")
        await self.cycle("response_release", i_response_ready=1)
        await self.wait()
        self.coverage.hit("response_stability")
        commit = dict(
            i_commit_context_id=0,
            i_commit_context_version=version,
            i_commit_package_id=7,
            i_commit_owner_id=0,
            i_commit_kernel_id=3,
            i_commit_epoch=2,
            i_commit_image_crc=image,
        )
        for _ in range(50):
            item = await self.cycle("commit", i_commit_valid=1, **commit)
            if item.pre["o_commit_ready"]:
                assert (
                    item.pre["o_shell_request_valid"]
                    and item.pre["o_shell_request_command"] == 3
                )
                break
        else:
            raise AssertionError("Commit not ready")
        self.inputs["i_commit_valid"] = 0
        for _ in range(100):
            item = await self.cycle("commit_ack")
            if item.post["o_commit_ack_valid"]:
                assert not item.post["o_commit_error"]
                assert item.post["o_active_context_version"] == version
                assert (
                    item.post["o_active_package_id"] == 7
                    and item.post["o_active_epoch"] == 2
                )
                break
        else:
            raise AssertionError("Commit acknowledgement missing")
        await self.cycle("ack_consume", i_commit_ack_ready=1)
        response = await self.request(1, expected_version=version)
        assert response["status"] == 1 and response["error_code"] == 14
        self.coverage.hit("activation_identity")
        # Cancellation must wait for a native response, then dirty the image.
        self.shell.delay = 20
        await self.send(5, context_id=1)
        for _ in range(10):
            item = await self.cycle("native_outstanding")
            if self.shell.pending:
                break
        assert self.shell.pending
        item = await self.cycle("cancel_start", i_cancel=1)
        assert not item.post["o_cancel_ack"]
        for _ in range(100):
            item = await self.cycle("cancel_drain")
            if item.post["o_cancel_ack"]:
                break
        else:
            raise AssertionError("Native cancellation failed to drain")
        await self.cycle("cancel_release", i_cancel=0)
        self.shell.delay = 3
        response = await self.request(3, context_id=1, expected_version=0)
        assert response["status"] == 1 and response["error_code"] == 14
        self.coverage.hit("dirty_cancel")
        _, version1, image1 = await self.load(context=1, package=8)
        response = await self.request(
            6,
            context_id=1,
            package_id=8,
            expected_version=version1,
            expected_crc=image1,
        )
        assert response["status"] == 0 and response["prepared"]
        response = await self.request(7, context_id=1)
        assert response["status"] == 0 and not response["prepared"]
        self.coverage.hit("rewrite_abort")
        self.coverage.goals = {
            name: bool(self.coverage.bins[name])
            for name in (
                "write_read_validate",
                "preflight_version",
                "prepare_no_activation",
                "response_stability",
                "activation_identity",
                "dirty_cancel",
                "rewrite_abort",
                "loading_package_identity",
            )
        }
