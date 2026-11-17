import tempfile
import unittest
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

from docx import Document as WordDocument
from fastapi.testclient import TestClient

from app.application import create_app
from app.config import MAX_UPLOAD_BYTES

EMPTY_CONTENT = {"ops": [{"insert": "\n"}]}


def build_docx(build):
    document = WordDocument()
    build(document)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "test.db"
        self.app = create_app(self.database_path)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.owner = {"X-User-Id": "1"}
        self.teammate = {"X-User-Id": "2"}
        self.stranger = {"X-User-Id": "3"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.directory.cleanup()

    def create(self):
        response = self.client.post("/api/documents", headers=self.owner, json={"title": "Team plan"})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_create_edit_share_reopen_and_revoke(self):
        document = self.create()
        path = f"/api/documents/{document['id']}"
        content = {"ops": [{"insert": "Important", "attributes": {"bold": True, "underline": True}},
                           {"insert": "\n", "attributes": {"header": 2}},
                           {"insert": "First item"}, {"insert": "\n", "attributes": {"list": "bullet"}}]}
        edited = self.client.put(path, headers=self.owner,
                                 json={"title": "Renamed plan", "content": content, "version": 1})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(self.client.get(path, headers=self.teammate).status_code, 404)
        shared = self.client.post(path + "/shares", headers=self.owner, json={"user_id": 2})
        self.assertEqual(shared.status_code, 201)
        reopened = self.client.get(path, headers=self.teammate).json()
        self.assertEqual(reopened["content"], content)
        self.assertEqual(reopened["title"], "Renamed plan")
        self.assertEqual(reopened["owner_id"], 1)
        listing = self.client.get("/api/documents", headers=self.teammate).json()
        self.assertEqual([row["id"] for row in listing], [document["id"]])
        self.assertEqual(self.client.get(path, headers=self.stranger).status_code, 404)
        self.assertEqual(self.client.post(path + "/shares", headers=self.teammate,
                                          json={"user_id": 3}).status_code, 403)
        edit = self.client.put(path, headers=self.teammate,
                               json={"title": "Sara's update", "content": content, "version": 2})
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(self.client.get(path, headers=self.owner).json()["title"], "Sara's update")
        self.assertEqual(self.client.delete(path + "/shares/2", headers=self.owner).status_code, 204)
        self.assertEqual(self.client.get(path, headers=self.teammate).status_code, 404)
        self.assertEqual(self.client.put(path, headers=self.teammate,
                                         json={"title": "Blocked", "content": content, "version": 3}).status_code, 404)

    def test_conflicting_save_does_not_overwrite(self):
        document = self.create()
        path = f"/api/documents/{document['id']}"
        payload = {"title": "First edit", "content": EMPTY_CONTENT, "version": 1}
        self.assertEqual(self.client.put(path, headers=self.owner, json=payload).status_code, 200)
        payload["title"] = "Stale edit"
        self.assertEqual(self.client.put(path, headers=self.owner, json=payload).status_code, 409)
        self.assertEqual(self.client.get(path, headers=self.owner).json()["title"], "First edit")

    def test_import_text_and_validate_files(self):
        response = self.client.post("/api/documents/import", headers=self.owner,
                                    files={"file": ("notes.txt", b"\xef\xbb\xbfHello\r\nteam", "text/plain")})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["title"], "notes")
        self.assertEqual(response.json()["content"]["ops"][0]["insert"], "Hello\nteam\n")
        for filename, content in [("x.pdf", b"hello"), ("x.txt", b"\xff"), ("x.txt", b" "), ("x.txt", b"a\x00b")]:
            with self.subTest(filename=filename, content=content):
                result = self.client.post("/api/documents/import", headers=self.owner,
                                           files={"file": (filename, content)})
                self.assertEqual(result.status_code, 400)
        too_large = self.client.post("/api/documents/import", headers=self.owner,
                                     files={"file": ("x.txt", b"a" * (MAX_UPLOAD_BYTES + 1))})
        self.assertEqual(too_large.status_code, 413)

    def test_validation_and_unsupported_content(self):
        document = self.create()
        path = f"/api/documents/{document['id']}"
        for content in [{"ops": [{"insert": {"image": "javascript:alert(1)"}}]},
                        {"ops": [{"insert": "x\n", "attributes": {"link": "javascript:alert(1)"}}]},
                        {"ops": [{"insert": "x"}]}, {"ops": []}]:
            with self.subTest(content=content):
                response = self.client.put(path, headers=self.owner,
                                            json={"title": "Valid", "content": content, "version": 1})
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.post("/api/documents", headers=self.owner,
                                          json={"title": "  "}).status_code, 422)
        self.assertEqual(self.client.get("/api/documents", headers={"X-User-Id": "100"}).status_code, 401)
        self.assertEqual(self.client.get("/api/documents").status_code, 422)

    def test_owner_validation_and_idempotent_sharing(self):
        document = self.create()
        path = f"/api/documents/{document['id']}/shares"
        self.assertEqual(self.client.post(path, headers=self.owner, json={"user_id": 1}).status_code, 400)
        self.assertEqual(self.client.post(path, headers=self.owner, json={"user_id": 999}).status_code, 404)
        for _ in range(2):
            self.assertEqual(self.client.post(path, headers=self.owner, json={"user_id": 2}).status_code, 201)
        self.assertEqual(len(self.client.get(path, headers=self.owner).json()), 1)

    def test_import_docx_preserves_formatting_and_rejects_empty(self):
        def build(document):
            document.add_heading("Section one", level=1)
            paragraph = document.add_paragraph()
            paragraph.add_run("Bold part").bold = True
            paragraph.add_run(" normal part")
            document.add_paragraph("First item", style="List Bullet")

        response = self.client.post("/api/documents/import", headers=self.owner,
                                    files={"file": ("plan.docx", build_docx(build),
                                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        self.assertEqual(response.status_code, 201)
        document = response.json()
        self.assertEqual(document["title"], "plan")
        ops = document["content"]["ops"]
        self.assertEqual(ops[0], {"insert": "Section one"})
        self.assertEqual(ops[1], {"insert": "\n", "attributes": {"header": 1}})
        self.assertEqual(ops[2], {"insert": "Bold part", "attributes": {"bold": True}})
        self.assertEqual(ops[3], {"insert": " normal part"})
        self.assertEqual(ops[-2], {"insert": "First item"})
        self.assertEqual(ops[-1], {"insert": "\n", "attributes": {"list": "bullet"}})

        empty = self.client.post("/api/documents/import", headers=self.owner,
                                 files={"file": ("empty.docx", build_docx(lambda document: None))})
        self.assertEqual(empty.status_code, 400)

        not_a_docx = self.client.post("/api/documents/import", headers=self.owner,
                                      files={"file": ("fake.docx", b"not a real docx")})
        self.assertEqual(not_a_docx.status_code, 400)

    def test_delete_document_removes_access_and_shares(self):
        document = self.create()
        path = f"/api/documents/{document['id']}"
        self.client.post(path + "/shares", headers=self.owner, json={"user_id": 2})
        self.assertEqual(self.client.delete(path, headers=self.teammate).status_code, 403)
        self.assertEqual(self.client.delete(path, headers=self.stranger).status_code, 404)
        self.assertEqual(self.client.delete(path, headers=self.owner).status_code, 204)
        self.assertEqual(self.client.get(path, headers=self.owner).status_code, 404)
        self.assertEqual(self.client.delete(path, headers=self.owner).status_code, 404)

    def test_persistence_across_application_restart(self):
        document = self.create()
        self.client.post(f"/api/documents/{document['id']}/shares", headers=self.owner, json={"user_id": 2})
        with TestClient(create_app(self.database_path)) as reopened:
            response = reopened.get(f"/api/documents/{document['id']}", headers=self.teammate)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["title"], "Team plan")

    def test_request_size_limit_and_static_app(self):
        response = self.client.post("/api/documents", headers=self.owner, content=b"x" * (2 * MAX_UPLOAD_BYTES + 1))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.assertIn("folio", self.client.get("/").text)
        self.assertEqual(self.client.get("/static/vendor/quill.js").status_code, 200)


    def test_create_is_committed_before_success_response(self):
        app = self.app
        database_path = self.database_path
        visible_counts = []

        async def observe_response(scope, receive, send):
            async def observe_send(message):
                if message["type"] == "http.response.start" and message["status"] == 201:
                    with sqlite3.connect(database_path) as db:
                        visible_counts.append(db.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
                await send(message)
            await app(scope, receive, observe_send)

        with TestClient(observe_response) as client:
            response = client.post("/api/documents", headers=self.owner, json={"title": "Durable save"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(visible_counts, [1])

    def test_app_instances_use_separate_databases(self):
        document = self.create()
        other_path = Path(self.directory.name) / "other.db"
        with TestClient(create_app(other_path)) as other:
            self.assertEqual(other.get("/api/documents", headers=self.owner).json(), [])
            self.assertEqual(other.get(f"/api/documents/{document['id']}", headers=self.owner).status_code, 404)
        self.assertEqual(len(self.client.get("/api/documents", headers=self.owner).json()), 1)

    def test_simultaneous_saves_have_one_winner(self):
        document = self.create()
        path = f"/api/documents/{document['id']}"

        def save(title):
            return self.client.put(path, headers=self.owner,
                                   json={"title": title, "content": EMPTY_CONTENT, "version": 1})

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(save, ["First writer", "Second writer"]))
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        saved = self.client.get(path, headers=self.owner).json()
        self.assertEqual(saved["version"], 2)
        winner = next(response.json() for response in responses if response.status_code == 200)
        self.assertEqual(saved["title"], winner["title"])

    def test_created_document_location_and_api_contract(self):
        response = self.client.post("/api/documents", headers=self.owner, json={"title": "Linked result"})
        self.assertEqual(response.headers["location"], f"/api/documents/{response.json()['id']}")
        self.assertEqual(self.client.get(response.headers["location"], headers=self.owner).status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/documents/{document_id}/shares", schema["paths"])
        self.assertEqual(schema["paths"]["/api/documents"]["get"]["tags"], ["Documents"])

    def test_frontend_module_imports_are_served(self):
        import re
        html = self.client.get("/").text
        self.assertIn('type="module" src="/static/js/app.js"', html)
        modules = ["app.js"]
        visited = set()
        while modules:
            name = modules.pop()
            if name in visited:
                continue
            visited.add(name)
            response = self.client.get("/static/js/" + name)
            self.assertEqual(response.status_code, 200, name)
            self.assertIn("javascript", response.headers["content-type"], name)
            modules.extend(re.findall(r'from "\./([^\"]+)"', response.text))
        self.assertGreaterEqual(len(visited), 8)


if __name__ == "__main__":
    unittest.main()
