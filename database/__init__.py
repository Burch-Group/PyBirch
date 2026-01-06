# PyBirch Database Module
# =======================
# SQLAlchemy-based database for managing laboratory data including:
# - Samples and their precursors
# - Fabrication procedures and equipment
# - Scan and queue templates
# - Executed scans and queues with measurement data
# - Analysis results

from database.models import (
    Base,
    Template,
    Equipment,
    Precursor,
    PrecursorInventory,
    Procedure,
    ProcedureEquipment,
    ProcedurePrecursor,
    Sample,
    SamplePrecursor,
    FabricationRun,
    FabricationRunEquipment,
    FabricationRunPrecursor,
    ScanTemplate,
    QueueTemplate,
    QueueTemplateItem,
    Queue,
    Scan,
    MeasurementObject,
    MeasurementDataPoint,
    MeasurementDataArray,
    AnalysisMethod,
    Analysis,
    AnalysisInput,
    AnalysisResult,
    Tag,
    EntityTag,
    Attachment,
    AuditLog,
)

from database.session import (
    DatabaseManager,
    get_db,
    init_db,
    get_session,
    close_db,
)

from database.crud import (
    SampleCRUD,
    ScanCRUD,
    QueueCRUD,
    TemplateCRUD,
    EquipmentCRUD,
    PrecursorCRUD,
    ProcedureCRUD,
    AnalysisCRUD,
    sample_crud,
    scan_crud,
    queue_crud,
    template_crud,
    equipment_crud,
    precursor_crud,
    procedure_crud,
    analysis_crud,
)

from database.extension import (
    DatabaseExtension,
    QueueDatabaseExtension,
)

from database.utils import (
    generate_sample_id,
    generate_scan_id,
    get_scan_data_as_dataframe,
    get_sample_scan_history,
    create_sample_from_template,
    add_tags_to_entity,
    get_entity_tags,
    search_samples,
    export_scan_to_csv,
    get_database_stats,
)

from database.services import (
    DatabaseService,
    get_db_service,
)

from database.uri_handler import (
    PyBirchURI,
    parse_pybirch_uri,
    generate_uri,
    URIHandler,
    get_uri_handler,
    setup_uri_handler_for_qt,
)

from database.weather import (
    get_weather_conditions,
    get_manual_weather_conditions,
    get_indoor_conditions,
)

__all__ = [
    # Models
    "Base",
    "Template",
    "Equipment",
    "Precursor",
    "PrecursorInventory",
    "Procedure",
    "ProcedureEquipment",
    "ProcedurePrecursor",
    "Sample",
    "SamplePrecursor",
    "FabricationRun",
    "FabricationRunEquipment",
    "FabricationRunPrecursor",
    "ScanTemplate",
    "QueueTemplate",
    "QueueTemplateItem",
    "Queue",
    "Scan",
    "MeasurementObject",
    "MeasurementDataPoint",
    "MeasurementDataArray",
    "AnalysisMethod",
    "Analysis",
    "AnalysisInput",
    "AnalysisResult",
    "Tag",
    "EntityTag",
    "Attachment",
    "AuditLog",
    # Session management
    "DatabaseManager",
    "get_db",
    "init_db",
    # CRUD operations
    "SampleCRUD",
    "ScanCRUD",
    "QueueCRUD",
    "TemplateCRUD",
    "EquipmentCRUD",
    "PrecursorCRUD",
    "ProcedureCRUD",
    "AnalysisCRUD",
    # Services
    "DatabaseService",
    "get_db_service",
    # URI handling
    "PyBirchURI",
    "parse_pybirch_uri",
    "generate_uri",
    "URIHandler",
    "get_uri_handler",
    "setup_uri_handler_for_qt",
    # Weather
    "get_weather_conditions",
    "get_manual_weather_conditions",
    "get_indoor_conditions",
]
