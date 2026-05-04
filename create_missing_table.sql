-- Create the missing AIDuplicateDetectionResult table
CREATE TABLE IF NOT EXISTS "audioDiagnostic_aiduplicatedetectionresult" (
    "id" bigserial NOT NULL PRIMARY KEY,
    "ai_provider" varchar(50) NOT NULL,
    "ai_model" varchar(100) NOT NULL,
    "processing_date" timestamp with time zone NOT NULL,
    "processing_time_seconds" double precision NOT NULL,
    "input_tokens" integer NOT NULL,
    "output_tokens" integer NOT NULL,
    "total_tokens" integer NOT NULL,
    "api_cost_usd" numeric(10, 4) NOT NULL,
    "duplicate_groups" jsonb NOT NULL,
    "duplicate_count" integer NOT NULL,
    "occurrences_to_delete" integer NOT NULL,
    "estimated_time_saved_seconds" double precision NOT NULL,
    "average_confidence" double precision NOT NULL,
    "high_confidence_count" integer NOT NULL,
    "detection_settings" jsonb NOT NULL,
    "paragraph_expansion_performed" boolean NOT NULL,
    "expanded_groups" jsonb NULL,
    "user_confirmed" boolean NOT NULL,
    "user_modified" boolean NOT NULL,
    "user_modifications" jsonb NULL,
    "audio_file_id" bigint NOT NULL,
    "user_id" integer NOT NULL
);

-- Add foreign key constraints
ALTER TABLE "audioDiagnostic_aiduplicatedetectionresult" 
ADD CONSTRAINT "audioDiagnostic_aidu_audio_file_id_7f7d6101_fk_audioDiag" 
FOREIGN KEY ("audio_file_id") REFERENCES "audioDiagnostic_audiofile" ("id") 
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "audioDiagnostic_aiduplicatedetectionresult" 
ADD CONSTRAINT "audioDiagnostic_aidu_user_id_b524f770_fk_auth_user" 
FOREIGN KEY ("user_id") REFERENCES "auth_user" ("id") 
DEFERRABLE INITIALLY DEFERRED;

-- Create indexes
CREATE INDEX IF NOT EXISTS "audioDiagnostic_aiduplicat_audio_file_id_7f7d6101" 
ON "audioDiagnostic_aiduplicatedetectionresult" ("audio_file_id");

CREATE INDEX IF NOT EXISTS "audioDiagnostic_aiduplicatedetectionresult_user_id_b524f770" 
ON "audioDiagnostic_aiduplicatedetectionresult" ("user_id");

CREATE INDEX IF NOT EXISTS "audioDiagno_audio_f_9d2897_idx" 
ON "audioDiagnostic_aiduplicatedetectionresult" ("audio_file_id", "processing_date" DESC);

CREATE INDEX IF NOT EXISTS "audioDiagno_user_id_70168f_idx" 
ON "audioDiagnostic_aiduplicatedetectionresult" ("user_id", "processing_date" DESC);

CREATE INDEX IF NOT EXISTS "audioDiagno_ai_prov_dd1e24_idx" 
ON "audioDiagnostic_aiduplicatedetectionresult" ("ai_provider", "ai_model");
