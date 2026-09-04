import { describe, it, expect, beforeEach, mock } from "bun:test";
import {
  enrollStudent,
  enrollStudentEmbedding,
  listStudents,
  deleteStudent,
  processAttendance,
  matchEmbeddings,
} from "../src/api.js";

describe("Frontend API Client", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("enrollStudentEmbedding", () => {
    it("sends JSON POST /api/students/enroll-embedding with correct payload", async () => {
      let capturedUrl = "";
      let capturedOptions = null;

      globalThis.fetch = async (url, options) => {
        capturedUrl = url;
        capturedOptions = options;
        return {
          ok: true,
          json: async () => ({
            id: 42,
            name: "Rahul Roy",
            roll_number: "CS101",
            class_name: "10-A",
            model_type: "faceapi",
          }),
        };
      };

      const mockEmbedding = Array(128).fill(0.05);
      const res = await enrollStudentEmbedding({
        name: "Rahul Roy",
        roll_number: "CS101",
        class_name: "10-A",
        embedding: mockEmbedding,
        model_type: "faceapi",
      });

      expect(capturedUrl).toBe("/api/students/enroll-embedding");
      expect(capturedOptions.method).toBe("POST");
      expect(capturedOptions.headers["Content-Type"]).toBe("application/json");

      const body = JSON.parse(capturedOptions.body);
      expect(body.name).toBe("Rahul Roy");
      expect(body.roll_number).toBe("CS101");
      expect(body.class_name).toBe("10-A");
      expect(body.model_type).toBe("faceapi");
      expect(body.embedding).toHaveLength(128);

      expect(res.id).toBe(42);
    });

    it("throws detailed error when response is not ok", async () => {
      globalThis.fetch = async () => ({
        ok: false,
        json: async () => ({ detail: "Roll number CS101 already enrolled." }),
      });

      expect(
        enrollStudentEmbedding({
          name: "Duplicate",
          roll_number: "CS101",
          class_name: "10-A",
          embedding: Array(128).fill(0),
        })
      ).rejects.toThrow("Roll number CS101 already enrolled.");
    });
  });

  describe("matchEmbeddings", () => {
    it("sends JSON POST /api/attendance/match-embeddings with correct payload", async () => {
      let capturedUrl = "";
      let capturedOptions = null;

      globalThis.fetch = async (url, options) => {
        capturedUrl = url;
        capturedOptions = options;
        return {
          ok: true,
          json: async () => ({
            session_id: 10,
            class_name: "10-A",
            attendance_date: "2026-09-05",
            total_faces: 2,
            recognized_count: 1,
            unknown_count: 1,
            records: [
              {
                student_id: 1,
                name: "Rahul Roy",
                roll_number: "CS101",
                class_name: "10-A",
                status: "present",
                similarity: 0.92,
                face_index: 0,
              },
            ],
            unmatched_faces: [
              {
                face_index: 1,
                status: "unknown",
              },
            ],
          }),
        };
      };

      const embeddings = [Array(128).fill(0.1), Array(128).fill(0.2)];
      const res = await matchEmbeddings({
        class_name: "10-A",
        attendance_date: "2026-09-05",
        embeddings,
        model_type: "faceapi",
        photo_hash: "abcd1234ef",
      });

      expect(capturedUrl).toBe("/api/attendance/match-embeddings");
      expect(capturedOptions.method).toBe("POST");
      expect(capturedOptions.headers["Content-Type"]).toBe("application/json");

      const body = JSON.parse(capturedOptions.body);
      expect(body.class_name).toBe("10-A");
      expect(body.attendance_date).toBe("2026-09-05");
      expect(body.model_type).toBe("faceapi");
      expect(body.photo_hash).toBe("abcd1234ef");
      expect(body.embeddings).toHaveLength(2);

      expect(res.session_id).toBe(10);
      expect(res.recognized_count).toBe(1);
    });

    it("throws error if matching fails", async () => {
      globalThis.fetch = async () => ({
        ok: false,
        json: async () => ({ detail: "No students enrolled in class 10-A" }),
      });

      expect(
        matchEmbeddings({
          class_name: "10-A",
          embeddings: [],
        })
      ).rejects.toThrow("No students enrolled in class 10-A");
    });
  });

  describe("enrollStudent (Cloud)", () => {
    it("posts FormData to /api/students/enroll", async () => {
      let capturedUrl = "";
      let capturedOptions = null;

      globalThis.fetch = async (url, options) => {
        capturedUrl = url;
        capturedOptions = options;
        return {
          ok: true,
          json: async () => ({ id: 5, name: "Student" }),
        };
      };

      const fd = new FormData();
      fd.append("name", "Student");
      const res = await enrollStudent(fd);

      expect(capturedUrl).toBe("/api/students/enroll");
      expect(capturedOptions.method).toBe("POST");
      expect(capturedOptions.body).toBe(fd);
      expect(res.id).toBe(5);
    });
  });

  describe("processAttendance (Cloud)", () => {
    it("posts FormData to /api/attendance/process", async () => {
      let capturedUrl = "";
      let capturedOptions = null;

      globalThis.fetch = async (url, options) => {
        capturedUrl = url;
        capturedOptions = options;
        return {
          ok: true,
          json: async () => ({ session_id: 1, total_faces: 3 }),
        };
      };

      const fd = new FormData();
      fd.append("class_name", "10-A");
      const res = await processAttendance(fd);

      expect(capturedUrl).toBe("/api/attendance/process");
      expect(capturedOptions.method).toBe("POST");
      expect(capturedOptions.body).toBe(fd);
      expect(res.session_id).toBe(1);
    });
  });
});
