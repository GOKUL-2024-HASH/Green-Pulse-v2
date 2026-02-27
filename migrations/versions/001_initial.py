"""Initial migration - create all tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create Enum types using DO...EXCEPTION block for idempotency
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE zonetype AS ENUM ('industrial', 'residential', 'roadside', 'ecologically_sensitive');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE stationstatus AS ENUM ('online', 'offline', 'maintenance');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tierlevel AS ENUM ('MONITOR', 'FLAG', 'VIOLATION');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE violationstatus AS ENUM ('MONITOR', 'FLAG', 'PENDING_OFFICER_REVIEW', 'ESCALATED', 'DISMISSED', 'RESOLVED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE officeractiontype AS ENUM ('ESCALATE', 'DISMISS', 'FLAG_FOR_MONITORING');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE userrole AS ENUM ('officer', 'supervisor', 'admin');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(200), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(200), nullable=False),
        sa.Column('full_name', sa.String(200), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('jurisdiction', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_role', 'users', ['role'])

    # Create stations table
    op.create_table(
        'stations',
        sa.Column('id', sa.String(20), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('waqi_id', sa.String(50), nullable=True),
        sa.Column('zone', sa.Text(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='online'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_stations_status', 'stations', ['status'])
    op.create_index('ix_stations_zone', 'stations', ['zone'])

    # Create pollutant_readings table
    op.create_table(
        'pollutant_readings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('station_id', sa.String(20), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('pm25', sa.Float(), nullable=True),
        sa.Column('pm10', sa.Float(), nullable=True),
        sa.Column('no2', sa.Float(), nullable=True),
        sa.Column('so2', sa.Float(), nullable=True),
        sa.Column('co', sa.Float(), nullable=True),
        sa.Column('o3', sa.Float(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('humidity', sa.Float(), nullable=True),
        sa.Column('wind_speed', sa.Float(), nullable=True),
        sa.Column('wind_direction', sa.Float(), nullable=True),
        sa.Column('pressure', sa.Float(), nullable=True),
        sa.Column('dew_point', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), server_default='true'),
        sa.Column('validation_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_pollutant_readings_station_timestamp', 'pollutant_readings', ['station_id', 'timestamp'])
    op.create_index('ix_pollutant_readings_timestamp', 'pollutant_readings', ['timestamp'])

    # Create rolling_averages table
    op.create_table(
        'rolling_averages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('station_id', sa.String(20), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('pollutant', sa.String(10), nullable=False),
        sa.Column('window_hours', sa.Integer(), nullable=False),
        sa.Column('average_value', sa.Float(), nullable=False),
        sa.Column('reading_count', sa.Integer(), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_rolling_averages_station_pollutant', 'rolling_averages', ['station_id', 'pollutant'])
    op.create_index('ix_rolling_averages_window', 'rolling_averages', ['window_start', 'window_end'])

    # Create compliance_events table
    op.create_table(
        'compliance_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('station_id', sa.String(20), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('pollutant', sa.String(10), nullable=False),
        sa.Column('tier', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('observed_value', sa.Float(), nullable=False),
        sa.Column('limit_value', sa.Float(), nullable=False),
        sa.Column('exceedance_percent', sa.Float(), nullable=False),
        sa.Column('averaging_period', sa.String(10), nullable=False),
        sa.Column('rule_name', sa.String(200), nullable=False),
        sa.Column('legal_reference', sa.String(500), nullable=True),
        sa.Column('rule_version', sa.String(50), nullable=True),
        sa.Column('met_context', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_compliance_events_station_pollutant', 'compliance_events', ['station_id', 'pollutant'])
    op.create_index('ix_compliance_events_status', 'compliance_events', ['status'])
    op.create_index('ix_compliance_events_tier', 'compliance_events', ['tier'])
    op.create_index('ix_compliance_events_created_at', 'compliance_events', ['created_at'])

    # Create violation_reports table
    op.create_table(
        'violation_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('compliance_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('compliance_events.id'), nullable=False),
        sa.Column('report_html', sa.Text(), nullable=True),
        sa.Column('report_pdf_path', sa.String(500), nullable=True),
        sa.Column('ledger_hash', sa.String(64), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_violation_reports_event_id', 'violation_reports', ['compliance_event_id'])

    # Create officer_actions table
    op.create_table(
        'officer_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('compliance_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('compliance_events.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action_type', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_officer_actions_event_id', 'officer_actions', ['compliance_event_id'])
    op.create_index('ix_officer_actions_user_id', 'officer_actions', ['user_id'])

    # Create audit_ledger table (immutable - INSERT only)
    op.create_table(
        'audit_ledger',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('sequence_number', sa.Integer(), nullable=False, unique=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_id', sa.String(200), nullable=False),
        sa.Column('event_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('prev_hash', sa.String(64), nullable=False),
        sa.Column('entry_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_audit_ledger_sequence', 'audit_ledger', ['sequence_number'])
    op.create_index('ix_audit_ledger_event_type', 'audit_ledger', ['event_type'])
    op.create_index('ix_audit_ledger_created_at', 'audit_ledger', ['created_at'])

    # CRITICAL: Enforce audit_ledger immutability via triggers.
    # REVOKE alone is insufficient when the app user is also the table owner —
    # owners bypass privilege checks in PostgreSQL. Triggers fire even for the
    # owner and cannot be bypassed without explicitly DROP TRIGGER.
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_ledger_immutable()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_ledger is immutable: % is not permitted on this table. (GreenPulse integrity constraint)',
                TG_OP;
        END;
        $$
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_audit_ledger_no_update ON audit_ledger;
        CREATE TRIGGER trg_audit_ledger_no_update
            BEFORE UPDATE ON audit_ledger
            FOR EACH ROW EXECUTE FUNCTION audit_ledger_immutable()
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_audit_ledger_no_delete ON audit_ledger;
        CREATE TRIGGER trg_audit_ledger_no_delete
            BEFORE DELETE ON audit_ledger
            FOR EACH ROW EXECUTE FUNCTION audit_ledger_immutable()
    """)

    # Seed default users
    # admin@greenpulse.in / admin123 (bcrypt hash)
    op.execute("""
        INSERT INTO users (id, email, hashed_password, full_name, role, jurisdiction, is_active)
        VALUES (
            gen_random_uuid(),
            'admin@greenpulse.in',
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/Levm8DwH36lLrIrVm',
            'System Administrator',
            'admin',
            'All India',
            true
        )
    """)

    # officer@greenpulse.in / officer123 (bcrypt hash)
    op.execute("""
        INSERT INTO users (id, email, hashed_password, full_name, role, jurisdiction, is_active)
        VALUES (
            gen_random_uuid(),
            'officer@greenpulse.in',
            '$2b$12$EFkXtHqHn6rHmxqL7C.Lw.6fQr.sWCWA1OjW8L7tHrVSyPxA7MNDC',
            'Field Officer Delhi',
            'officer',
            'Delhi',
            true
        )
    """)


def downgrade() -> None:
    op.drop_table('audit_ledger')
    op.drop_table('officer_actions')
    op.drop_table('violation_reports')
    op.drop_table('compliance_events')
    op.drop_table('rolling_averages')
    op.drop_table('pollutant_readings')
    op.drop_table('stations')
    op.drop_table('users')

    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS officeractiontype")
    op.execute("DROP TYPE IF EXISTS violationstatus")
    op.execute("DROP TYPE IF EXISTS tierlevel")
    op.execute("DROP TYPE IF EXISTS stationstatus")
    op.execute("DROP TYPE IF EXISTS zonetype")
