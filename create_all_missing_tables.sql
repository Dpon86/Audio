-- Create all missing tables from migration 0018
-- Using IF NOT EXISTS to safely create only missing tables

-- Table: AIPDFComparisonResult
CREATE TABLE IF NOT EXISTS "audioDiagnostic_aipdfcomparisonresult" (
    "id" bigserial NOT NULL PRIMARY KEY,
    "ai_provider" varchar(50) NOT NULL,
    "ai_model" varchar(100) NOT NULL,
    "processing_date" timestamp with time zone NOT NULL,
    "processing_time_seconds" double precision NOT NULL,
    "input_tokens" integer NOT NULL,
    "output_tokens" integer NOT NULL,
    "total_tokens" integer NOT NULL,
    "api_cost_usd" numeric(10, 4) NOT NULL,
    "alignment_result" jsonb NOT NULL,
    "discrepancies" jsonb NOT NULL,
    "coverage_percentage" double precision NOT NULL,
    "total_discrepancies" integer NOT NULL,
    "missing_in_audio_count" integer NOT NULL,
    "extra_in_audio_count" integer NOT NULL,
    "paraphrased_count" integer NOT NULL,
    "high_severity_count" integer NOT NULL,
    "medium_severity_count" integer NOT NULL,
    "low_severity_count" integer NOT NULL,
    "overall_quality" varchar(20) NOT NULL,
    "confidence_score" double precision NOT NULL,
    "clean_transcript_marked" text NOT NULL,
    "reviewed" boolean NOT NULL,
    "review_notes" text NULL,
    "audio_file_id" bigint NOT NULL,
    "project_id" bigint NOT NULL,
    "user_id" integer NOT NULL
);

-- Table: AIProcessingLog
CREATE TABLE IF NOT EXISTS "audioDiagnostic_aiprocessinglog" (
    "id" bigserial NOT NULL PRIMARY KEY,
    "ai_provider" varchar(50) NOT NULL,
    "ai_model" varchar(100) NOT NULL,
    "task_type" varchar(50) NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    "request_data_preview" text NULL,
    "data_sent_bytes" integer NOT NULL,
    "input_tokens" integer NOT NULL,
    "output_tokens" integer NOT NULL,
    "total_tokens" integer NOT NULL,
    "processing_time_seconds" double precision NOT NULL,
    "cost_usd" numeric(10, 4) NOT NULL,
    "status" varchar(20) NOT NULL,
    "error_message" text NULL,
    "user_consented" boolean NOT NULL,
    "data_sanitized" boolean NOT NULL,
    "audio_file_id" bigint NULL,
    "project_id" bigint NULL,
    "user_id" integer NOT NULL
);

-- Table: DuplicateAnalysis
CREATE TABLE IF NOT EXISTS "audioDiagnostic_duplicateanalysis" (
    "id" bigserial NOT NULL PRIMARY KEY,
    "filename" varchar(255) NOT NULL,
    "duplicate_groups" jsonb NOT NULL,
    "algorithm" varchar(50) NOT NULL,
    "total_segments" integer NOT NULL,
    "duplicate_count" integer NOT NULL,
    "duplicate_groups_count" integer NOT NULL,
    "selected_deletions" jsonb NULL,
    "assembly_info" jsonb NULL,
    "created_at" timestamp with time zone NOT NULL,
    "updated_at" timestamp with time zone NOT NULL,
    "metadata" jsonb NULL,
    "audio_file_id" bigint NULL,
    "project_id" bigint NOT NULL
);

-- Add foreign keys for AIPDFComparisonResult
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audioDiagnostic_aipd_audio_file_id_c4f4b3e9_fk_audioDiag') THEN
        ALTER TABLE "audioDiagnostic_aipdfcomparisonresult" 
        ADD CONSTRAINT "audioDiagnostic_aipd_audio_file_id_c4f4b3e9_fk_audioDiag" 
        FOREIGN KEY ("audio_file_id") REFERENCES "audioDiagnostic_audiofile" ("id") 
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audioDiagnostic_aipd_project_id_c935bc80_fk_audioDiag') THEN
        ALTER TABLE "audioDiagnostic_aipdfcomparisonresult" 
        ADD CONSTRAINT "audioDiagnostic_aipd_project_id_c935bc80_fk_audioDiag" 
        FOREIGN KEY ("project_id") REFERENCES "audioDiagnostic_audioproject" ("id") 
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audioDiagnostic_aipd_user_id_2ce16e07_fk_auth_user') THEN
        ALTER TABLE "audioDiagnostic_aipdfcomparisonresult" 
        ADD CONSTRAINT "audioDiagnostic_aipd_user_id_2ce16e07_fk_auth_user" 
        FOREIGN KEY ("user_id") REFERENCES "auth_user" ("id") 
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

-- Add foreign keys for AIProcessingLog
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audioDiagnostic_aipr_audio_file_id_c0ecdf5a_fk_audioDiag') THEN
        ALTER TABLE "audioDiagnostic_aiprocessinglog" 
        ADD CONSTRAINT "audioDiagnostic_aipr_audio_file_id_c0ecdf5a_fk_audioDiag" 
        FOREIGN KEY ("audio_file_id") REFERENCES "audioDiagnostic_audiofile" ("id") 
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audioDiagnostic_aipr_project_id_43ffe6fb_fk_audioDiag') THEN
        ALTER TABLE "audioDiagnostic_aiprocessinglog" 
        ADD CONSTRAINT "audioDiagnostic_aipr_project_id_43ffe6fb_fk_audioDiag" 
        FOREIGN KEY ("project_id") REFERENCES "audioDiagnostic_audioproject" ("id") 
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audioDiagnostic_aipr_user_id_e39afacb_fk_auth_user') THEN
        ALTER TABLE "audioDiagnostic_aiprocessinglog" 
        ADD CONSTRAINT "audioDiagnostic_aipr_user_id_e39afacb_fk_auth_user" 
        FOREIGN KEY ("user_id") REFERENCES "auth_user" ("id") 
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

-- Add foreign keys for DuplicateAnalysis
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audioDiagnostic_dupl_audio_file_id_87aa1530_fk_audioDiag') THEN
        ALTER TABLE "audioDiagnostic_duplicateanalysis" 
        ADD CONSTRAINT "audioDiagnostic_dupl_audio_file_id_87aa1530_fk_audioDiag" 
        FOREIGN KEY ("audio_file_id") REFERENCES "audioDiagnostic_audiofile" ("id") 
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audioDiagnostic_dupl_project_id_e3cc7c88_fk_audioDiag') THEN
        ALTER TABLE "audioDiagnostic_duplicateanalysis" 
        ADD CONSTRAINT "audioDiagnostic_dupl_project_id_e3cc7c88_fk_audioDiag" 
        FOREIGN KEY ("project_id") REFERENCES "audioDiagnostic_audioproject" ("id") 
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

-- Create indexes for AIPDFComparisonResult
CREATE INDEX IF NOT EXISTS "audioDiagnostic_aipdfcomparisonresult_audio_file_id_c4f4b3e9" 
ON "audioDiagnostic_aipdfcomparisonresult" ("audio_file_id");

CREATE INDEX IF NOT EXISTS "audioDiagnostic_aipdfcomparisonresult_project_id_c935bc80" 
ON "audioDiagnostic_aipdfcomparisonresult" ("project_id");

CREATE INDEX IF NOT EXISTS "audioDiagnostic_aipdfcomparisonresult_user_id_2ce16e07" 
ON "audioDiagnostic_aipdfcomparisonresult" ("user_id");

CREATE INDEX IF NOT EXISTS "audioDiagno_audio_f_ea66e8_idx" 
ON "audioDiagnostic_aipdfcomparisonresult" ("audio_file_id", "processing_date" DESC);

CREATE INDEX IF NOT EXISTS "audioDiagno_project_e3a76d_idx" 
ON "audioDiagnostic_aipdfcomparisonresult" ("project_id", "processing_date" DESC);

CREATE INDEX IF NOT EXISTS "audioDiagno_user_id_1b8685_idx" 
ON "audioDiagnostic_aipdfcomparisonresult" ("user_id", "processing_date" DESC);

-- Create indexes for AIProcessingLog
CREATE INDEX IF NOT EXISTS "audioDiagnostic_aiprocessinglog_audio_file_id_c0ecdf5a" 
ON "audioDiagnostic_aiprocessinglog" ("audio_file_id");

CREATE INDEX IF NOT EXISTS "audioDiagnostic_aiprocessinglog_project_id_43ffe6fb" 
ON "audioDiagnostic_aiprocessinglog" ("project_id");

CREATE INDEX IF NOT EXISTS "audioDiagnostic_aiprocessinglog_user_id_e39afacb" 
ON "audioDiagnostic_aiprocessinglog" ("user_id");

CREATE INDEX IF NOT EXISTS "audioDiagno_user_id_66d5ba_idx" 
ON "audioDiagnostic_aiprocessinglog" ("user_id", "timestamp" DESC);

CREATE INDEX IF NOT EXISTS "audioDiagno_audio_f_4eafd2_idx" 
ON "audioDiagnostic_aiprocessinglog" ("audio_file_id", "timestamp" DESC);

CREATE INDEX IF NOT EXISTS "audioDiagno_task_ty_3abd90_idx" 
ON "audioDiagnostic_aiprocessinglog" ("task_type", "timestamp" DESC);

CREATE INDEX IF NOT EXISTS "audioDiagno_status_bbe1e9_idx" 
ON "audioDiagnostic_aiprocessinglog" ("status");

-- Create indexes for DuplicateAnalysis
CREATE INDEX IF NOT EXISTS "audioDiagnostic_duplicateanalysis_audio_file_id_87aa1530" 
ON "audioDiagnostic_duplicateanalysis" ("audio_file_id");

CREATE INDEX IF NOT EXISTS "audioDiagnostic_duplicateanalysis_project_id_e3cc7c88" 
ON "audioDiagnostic_duplicateanalysis" ("project_id");

CREATE INDEX IF NOT EXISTS "audioDiagno_project_86a55c_idx" 
ON "audioDiagnostic_duplicateanalysis" ("project_id", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "audioDiagno_audio_f_0c0b10_idx" 
ON "audioDiagnostic_duplicateanalysis" ("audio_file_id");

CREATE INDEX IF NOT EXISTS "audioDiagno_filenam_a59d71_idx" 
ON "audioDiagnostic_duplicateanalysis" ("filename");
