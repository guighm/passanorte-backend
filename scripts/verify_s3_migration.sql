DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM auth.users
        WHERE id = 'employee-s2' AND role = 'supplier' AND NOT is_active AND partner_id IS NULL
    ) OR NOT EXISTS (
        SELECT FROM auth.refresh_sessions WHERE user_id = 'employee-s2' AND revoked
    ) OR NOT EXISTS (
        SELECT FROM auth.audit_logs WHERE entity_id = 'employee-s2' AND action = 'supplier_missing_partner_s3'
    ) OR NOT EXISTS (
        SELECT FROM gamification.audit_logs WHERE id = 'audit-s2' AND actor_id = 'employee-s2'
    ) THEN
        RAISE EXCEPTION 'Legacy identity quarantine, sessions, report or history did not survive the S3 upgrade';
    END IF;
    IF (SELECT count(*) FROM catalog.categories WHERE name IN ('Lazer', 'Cultura', 'Gastronomia')) <> 3 THEN
        RAISE EXCEPTION 'S3 catalog categories are missing';
    END IF;
END $$;
