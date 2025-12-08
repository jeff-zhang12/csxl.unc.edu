"""Tests for the HiringService class."""

# PyTest
import pytest
from unittest.mock import create_autospec

from backend.services.exceptions import (
    UserPermissionException,
    ResourceNotFoundException,
    CoursePermissionException,
)

# Tested Dependencies
from .....models.academics.hiring.application_review import (
    HiringStatus,
    ApplicationReviewOverview,
    ApplicationReviewStatus,
)
from .....services.academics import HiringService
from .....services.application import ApplicationService
from .....services.academics.course_site import CourseSiteService
from .....entities.academics.section_entity import SectionEntity
from .....entities.academics.hiring.application_review_entity import (
    ApplicationReviewEntity,
)
from .....entities.academics.hiring.hiring_assignment_entity import HiringAssignmentEntity, HiringAssignmentStatus
from .....entities.academics.hiring.hiring_level_entity import HiringLevelEntity
from .....entities.office_hours import CourseSiteEntity
from .....entities.section_application_table import section_application_table
from .....models.academics.hiring.hiring_assignment_audit import (
    HiringAssignmentAuditOverview,
)
from .....models.academics.hiring.hiring_assignment import HiringAssignmentFlagFilter

from sqlalchemy import select, delete, text
from sqlalchemy.orm import Session


# Injected Service Fixtures
from .fixtures import hiring_svc
from ..course_site_test import course_site_svc

# Import the setup_teardown fixture explicitly to load entities in database
from ...core_data import setup_insert_data_fixture as insert_order_0
from ...academics.term_data import fake_data_fixture as insert_order_1
from ...academics.course_data import fake_data_fixture as insert_order_2
from ...academics.section_data import fake_data_fixture as insert_order_3
from ...room_data import fake_data_fixture as insert_order_4
from ...office_hours.office_hours_data import fake_data_fixture as insert_order_5
from .hiring_data import fake_data_fixture as insert_order_6

from backend.models.pagination import PaginationParams


# Test data
from ... import user_data
from ...academics import section_data, term_data
from ...office_hours import office_hours_data
from . import hiring_data

__authors__ = ["Ajay Gandecha"]
__copyright__ = "Copyright 2024"
__license__ = "MIT"

# Test Functions


def test_get_status(hiring_svc: HiringService):
    """Test that an instructor can get status on hiring."""
    hiring_status = hiring_svc.get_status(
        user_data.instructor, office_hours_data.comp_110_site.id
    )
    assert isinstance(hiring_status, HiringStatus)
    assert len(hiring_status.not_preferred) == 1
    assert (
        hiring_status.not_preferred[0].application_id == hiring_data.application_one.id
    )
    assert len(hiring_status.preferred) == 1
    assert hiring_status.preferred[0].application_id == hiring_data.application_two.id
    assert len(hiring_status.not_processed) == 2
    assert (
        hiring_status.not_processed[0].application_id
        == hiring_data.application_three.id
    )
    assert (
        hiring_status.not_processed[1].application_id == hiring_data.application_four.id
    )


def test_get_status_site_not_found(hiring_svc: HiringService):
    """Ensures that hiring is not possible if a course site does not exist."""
    with pytest.raises(ResourceNotFoundException):
        hiring_svc.get_status(user_data.instructor, 404)
        pytest.fail()


def test_get_status_site_not_instructor(hiring_svc: HiringService):
    """Ensures that hiring information can only be viwed by instructors."""
    with pytest.raises(UserPermissionException):
        hiring_svc.get_status(user_data.ambassador, office_hours_data.comp_110_site.id)
        pytest.fail()


def test_get_status_with_permission(hiring_svc: HiringService):
    """Ensures that hiring information can only be viwed by instructors."""
    status = hiring_svc.get_status(user_data.root, office_hours_data.comp_110_site.id)
    assert status is not None


def test_update_status(hiring_svc: HiringService):
    """Test that an instructor can update the hiring status."""
    status = hiring_svc.get_status(
        user_data.instructor, office_hours_data.comp_110_site.id
    )

    status.not_preferred[0].status = ApplicationReviewStatus.PREFERRED
    status.not_preferred[0].preference = 1
    status.preferred[0].notes = "Updated notes!"
    status.preferred[0].level = hiring_data.uta_level
    status.not_processed[0].preference = 1
    status.not_processed[1].preference = 0

    new_status = hiring_svc.update_status(
        user_data.instructor, office_hours_data.comp_110_site.id, status
    )

    assert len(new_status.not_preferred) == 0
    assert len(new_status.preferred) == 2
    assert new_status.preferred[0].application_id == hiring_data.application_two.id
    assert new_status.preferred[0].notes == "Updated notes!"
    assert new_status.preferred[0].level.id == hiring_data.uta_level.id
    assert new_status.preferred[1].application_id == hiring_data.application_one.id
    assert new_status.not_processed[0].application_id == hiring_data.application_four.id
    assert (
        new_status.not_processed[1].application_id == hiring_data.application_three.id
    )


def test_update_status_site_not_found(hiring_svc: HiringService):
    """Ensures that updating hiring is not possible if a course site does not exist."""
    status = hiring_svc.get_status(
        user_data.instructor, office_hours_data.comp_110_site.id
    )
    with pytest.raises(ResourceNotFoundException):
        hiring_svc.update_status(user_data.instructor, 404, status)
        pytest.fail()


def test_update_status_site_not_instructor(hiring_svc: HiringService):
    """Ensures that updating hiring information can only be viwed by instructors."""
    status = hiring_svc.get_status(
        user_data.instructor, office_hours_data.comp_110_site.id
    )
    with pytest.raises(UserPermissionException):
        hiring_svc.update_status(
            user_data.ambassador, office_hours_data.comp_110_site.id, status
        )
        pytest.fail()


def test_update_status_administrator(hiring_svc: HiringService):
    status = hiring_svc.get_status(
        user_data.instructor, office_hours_data.comp_110_site.id
    )
    hiring_svc.update_status(user_data.root, office_hours_data.comp_110_site.id, status)
    assert True


def test_get_hiring_admin_overview(hiring_svc: HiringService):
    """Ensures that the admin is able to get the hiring admin data."""
    hiring_admin_overview = hiring_svc.get_hiring_admin_overview(
        user_data.root, term_data.current_term.id
    )
    assert hiring_admin_overview is not None
    assert len(hiring_admin_overview.sites) == 2


def test_get_hiring_admin_overview_checks_permission(hiring_svc: HiringService):
    """Ensures that nobody else is able to check the hiring data."""
    with pytest.raises(UserPermissionException):
        hiring_svc.get_hiring_admin_overview(
            user_data.ambassador, term_data.current_term.id
        )
        pytest.fail()


def test_create_hiring_assignment(hiring_svc: HiringService):
    """Ensures that the admin can create hiring assignments."""
    assignment = hiring_svc.create_hiring_assignment(
        user_data.root, hiring_data.new_hiring_assignment
    )
    assert assignment is not None


def test_create_hiring_assignment_checks_permission(hiring_svc: HiringService):
    """Ensures that nobody else is able to modify hiring data."""
    with pytest.raises(UserPermissionException):
        hiring_svc.create_hiring_assignment(
            user_data.ambassador, hiring_data.new_hiring_assignment
        )
        pytest.fail()


def test_update_hiring_assignment(hiring_svc: HiringService):
    """Ensures that the admin can update hiring assignments."""
    assignment = hiring_svc.update_hiring_assignment(
        user_data.root, hiring_data.updated_hiring_assignment
    )
    assert assignment is not None
    assert assignment.id == hiring_data.updated_hiring_assignment.id


def test_update_hiring_assignment_checks_permission(hiring_svc: HiringService):
    """Ensures that nobody else is able to modify hiring data."""
    with pytest.raises(UserPermissionException):
        hiring_svc.update_hiring_assignment(
            user_data.ambassador, hiring_data.updated_hiring_assignment
        )
        pytest.fail()


def test_update_hiring_assignment_not_found(hiring_svc: HiringService):
    """Ensures that hiring data cannot be updated if it does not exist."""
    with pytest.raises(ResourceNotFoundException):
        hiring_svc.update_hiring_assignment(
            user_data.root, hiring_data.new_hiring_assignment
        )
        pytest.fail()


def test_update_hiring_assigment_flag(hiring_svc: HiringService):
    """Ensures that the admin can update the flagged status of a hiring assignment."""
    assignment = hiring_svc.update_hiring_assignment(
        user_data.root, hiring_data.hiring_assignment_flagged
    )
    assert assignment is not None
    assert assignment.flagged is True


def test_delete_hiring_assignment(hiring_svc: HiringService):
    """Ensures that the admin can delete hiring assignments."""
    hiring_svc.delete_hiring_assignment(
        user_data.root, hiring_data.hiring_assignment.id
    )


def test_delete_hiring_assignment_checks_permission(hiring_svc: HiringService):
    """Ensures that nobody else is able to modify hiring data."""
    with pytest.raises(UserPermissionException):
        hiring_svc.delete_hiring_assignment(
            user_data.ambassador, hiring_data.hiring_assignment.id
        )
        pytest.fail()


def test_delete_hiring_assignment_not_found(hiring_svc: HiringService):
    """Ensures that hiring data cannot be deleted if it does not exist."""
    with pytest.raises(ResourceNotFoundException):
        hiring_svc.delete_hiring_assignment(
            user_data.root, hiring_data.new_hiring_assignment.id
        )
        pytest.fail()


def test_get_hiring_levels(hiring_svc: HiringService):
    """Ensures that the admin can see all hiring levels."""
    levels = hiring_svc.get_hiring_levels(user_data.root)
    assert levels is not None
    assert len(levels) == 1


def test_get_hiring_level_checks_permission(hiring_svc: HiringService):
    """Ensures that nobody else is able see hiring levels."""
    with pytest.raises(UserPermissionException):
        hiring_svc.get_hiring_levels(user_data.ambassador)
        pytest.fail()


def test_create_hiring_level(hiring_svc: HiringService):
    """Ensures that the admin can create hiring levels."""
    level = hiring_svc.create_hiring_level(user_data.root, hiring_data.new_level)
    assert level is not None


def test_create_hiring_level_checks_permission(hiring_svc: HiringService):
    """Ensures that nobody else is able to modify hiring data."""
    with pytest.raises(UserPermissionException):
        hiring_svc.create_hiring_level(user_data.ambassador, hiring_data.new_level)
        pytest.fail()


def test_update_hiring_level(hiring_svc: HiringService):
    """Ensures that the admin can update hiring levels."""
    level = hiring_svc.update_hiring_level(
        user_data.root, hiring_data.updated_uta_level
    )
    assert level is not None
    assert level.id == hiring_data.updated_uta_level.id


def test_update_hiring_level_checks_permission(hiring_svc: HiringService):
    """Ensures that nobody else is able to modify hiring data."""
    with pytest.raises(UserPermissionException):
        hiring_svc.update_hiring_level(
            user_data.ambassador, hiring_data.updated_uta_level
        )
        pytest.fail()


def test_update_hiring_level_not_found(hiring_svc: HiringService):
    """Ensures that hiring data cannot be deleted if it does not exist."""
    with pytest.raises(ResourceNotFoundException):
        hiring_svc.update_hiring_level(user_data.root, hiring_data.new_level)
        pytest.fail()


def test_create_missing_course_sites_for_term(
    hiring_svc: HiringService, course_site_svc: CourseSiteService
):
    user = user_data.root
    term = term_data.current_term
    overview_pre = hiring_svc.get_hiring_admin_overview(user, term.id)
    hiring_svc.create_missing_course_sites_for_term(user, term.id)
    overview_post = hiring_svc.get_hiring_admin_overview(user, term.id)
    assert len(overview_post.sites) > len(overview_pre.sites)


def test_get_phd_applicants(hiring_svc: HiringService):
    user = user_data.root
    term = term_data.current_term
    applicants = hiring_svc.get_phd_applicants(user, term.id)
    assert len(applicants) > 0
    for applicant in applicants:
        assert applicant.program_pursued in {"PhD", "PhD (ABD)"}


def test_get_course_site_total_enrollment(hiring_svc: HiringService, session: Session):
    """Verify total enrollment sums section enrollments for a course site."""
    from ...office_hours import office_hours_data

    course_site_id = office_hours_data.comp_110_site.id
    total = hiring_svc.get_course_site_total_enrollment(
        user_data.instructor, course_site_id
    )
    sections = session.scalars(
        select(SectionEntity).where(SectionEntity.course_site_id == course_site_id)
    ).all()
    expected = sum(s.enrolled for s in sections)
    assert total == expected


def test_get_course_site_total_enrollment_checks_permission(hiring_svc: HiringService):
    """Ambassador should not be able to read instructor-only enrollment."""
    from ...office_hours import office_hours_data

    with pytest.raises(UserPermissionException):
        hiring_svc.get_course_site_total_enrollment(
            user_data.ambassador, office_hours_data.comp_110_site.id
        )
        pytest.fail()
def test_get_hiring_summary_overview_all(hiring_svc: HiringService):
    """Test that the hiring summary overview returns all assignments."""
    term_id = term_data.current_term.id
    pagination_params = PaginationParams(page=0, page_size=10, order_by="", filter="")
    summary = hiring_svc.get_hiring_summary_overview(
        user_data.root, term_id, "all", pagination_params
    )
    assert summary is not None
    assert len(summary.items) > 0
    assert all(assignment.flagged in [True, False] for assignment in summary.items)


def test_get_hiring_summary_overview_flagged(hiring_svc: HiringService):
    """Test that the hiring summary overview filters for flagged assignments."""
    term_id = term_data.current_term.id
    pagination_params = PaginationParams(page=0, page_size=10, order_by="", filter="")
    summary = hiring_svc.get_hiring_summary_overview(
        user_data.root, term_id, HiringAssignmentFlagFilter.FLAGGED, pagination_params
    )
    assert summary is not None
    assert len(summary.items) > 0
    assert all(assignment.flagged is True for assignment in summary.items)


def test_get_hiring_summary_overview_not_flagged(hiring_svc: HiringService):
    """Test that the hiring summary overview filters for not flagged assignments."""
    term_id = term_data.current_term.id
    pagination_params = PaginationParams(page=0, page_size=10, order_by="", filter="")
    summary = hiring_svc.get_hiring_summary_overview(
        user_data.root, term_id, HiringAssignmentFlagFilter.NOT_FLAGGED, pagination_params
    )
    assert summary is not None
    assert len(summary.items) > 0
    assert all(assignment.flagged is False for assignment in summary.items)


def test_get_hiring_summary_overview_invalid_flagged(hiring_svc: HiringService):
    """Test that an invalid flagged filter returns all flagged/non-flagged assignments."""
    term_id = term_data.current_term.id
    pagination_params = PaginationParams(page=0, page_size=10, order_by="", filter="")
    summary = hiring_svc.get_hiring_summary_overview(
        user_data.root, term_id, "invalid_flagged", pagination_params
    )

    assert len(summary.items) > 0
    assert all(assignment.flagged in [True, False] for assignment in summary.items)


def test_update_hiring_assignment_creates_audit_log(hiring_svc: HiringService):
    """Ensures that updating an assignment creates an audit log entry."""
    hiring_svc.update_hiring_assignment(
        user_data.root, hiring_data.updated_hiring_assignment
    )

    history = hiring_svc.get_audit_history(
        user_data.root, hiring_data.hiring_assignment.id
    )

    assert len(history) == 1
    assert history[0].changed_by_user.id == user_data.root.id
    assert "Status: COMMIT -> FINAL" in history[0].change_details


def test_update_hiring_assignment_audit_details_notes(hiring_svc: HiringService):
    """Ensures notes updates are formatted correctly using the 'Old -> New' format."""
    assignment = hiring_data.hiring_assignment.model_copy()
    assignment.notes = "New Notes Value"

    hiring_svc.update_hiring_assignment(user_data.root, assignment)

    history = hiring_svc.get_audit_history(user_data.root, assignment.id)
    assert len(history) == 1
    assert "Notes: 'Some notes here' -> 'New Notes Value'" in history[0].change_details


def test_update_hiring_assignment_audit_details_flagged(hiring_svc: HiringService):
    """Ensures flagged status changes are logged."""
    assignment = hiring_data.hiring_assignment.model_copy()
    assignment.flagged = True

    hiring_svc.update_hiring_assignment(user_data.root, assignment)

    history = hiring_svc.get_audit_history(user_data.root, assignment.id)
    assert len(history) == 1
    assert "Flagged: False -> True" in history[0].change_details


def test_get_audit_history_ordering(hiring_svc: HiringService):
    """Ensures audit logs are returned in reverse chronological order (newest first)."""
    a1 = hiring_data.hiring_assignment.model_copy()
    a1.position_number = "update_1"
    hiring_svc.update_hiring_assignment(user_data.root, a1)

    a2 = hiring_data.hiring_assignment.model_copy()
    a2.position_number = "update_2"
    hiring_svc.update_hiring_assignment(user_data.root, a2)

    history = hiring_svc.get_audit_history(
        user_data.root, hiring_data.hiring_assignment.id
    )

    assert len(history) == 2
    assert "update_2" in history[0].change_details
    assert "update_1" in history[1].change_details


def test_get_audit_history_permissions(hiring_svc: HiringService):
    """Ensures that non-admins cannot view audit history."""
    with pytest.raises(UserPermissionException):
        hiring_svc.get_audit_history(
            user_data.student, hiring_data.hiring_assignment.id
        )

def test_run_autohire_respects_student_preference(hiring_svc: HiringService, session: Session):
    """
    Ensures that the student preferences are the tie breakers in automatically creating assignments
    when multiple instructors prefer the same student.

    Scenario: Student A ranks Course 1 (#1) and Course 2 (#2). Instructors prefer A for both.
    Expected: Student A is assigned to Course 1 (their #1 choice).
    """
    from .....entities.application_entity import ApplicationEntity
    
    admin = user_data.root
    term_id = term_data.current_term.id
    student = user_data.student
    
    session.execute(text("SELECT setval('academics__hiring__assignment_id_seq', 100, true)"))
    session.commit()

    session.execute(
        delete(HiringAssignmentEntity)
        .where(HiringAssignmentEntity.user_id == student.id)
    )
    session.flush()

    site_1 = session.get(CourseSiteEntity, office_hours_data.comp_301_site.id) 
    site_2 = session.get(CourseSiteEntity, office_hours_data.comp_110_site.id)
    
    s1 = SectionEntity(
        term_id=term_id, course_id="comp301", number="999", 
        course_site_id=site_1.id, 
        total_seats=100, enrolled=65, 
        meeting_pattern="MWF"
    )
    s2 = SectionEntity(
        term_id=term_id, course_id="comp110", number="999", 
        course_site_id=site_2.id, 
        total_seats=100, enrolled=65, 
        meeting_pattern="MWF"
    )
    session.add_all([s1, s2])
    session.commit()

    fresh_app = ApplicationEntity(
        user_id=student.id,
        term_id=term_id,
        type="new_uta", 
        program_pursued="CS",
        academic_hours=15,
        gpa=4.0
    )
    session.add(fresh_app)
    session.commit()

    session.execute(section_application_table.insert().values(
        application_id=fresh_app.id,
        section_id=s1.id,
        preference=0
    ))

    session.execute(section_application_table.insert().values(
        application_id=fresh_app.id,
        section_id=s2.id,
        preference=1
    ))
    session.commit()

    level = session.scalar(select(HiringLevelEntity).limit(1))
    
    rev1 = ApplicationReviewEntity(
        application_id=fresh_app.id,
        course_site_id=site_1.id,
        status=ApplicationReviewStatus.PREFERRED,
        preference=0,
        level_id=level.id,
        notes=""
    )
    rev2 = ApplicationReviewEntity(
        application_id=fresh_app.id,
        course_site_id=site_2.id,
        status=ApplicationReviewStatus.PREFERRED,
        preference=0,
        level_id=level.id,
        notes=""
    )
    session.add_all([rev1, rev2])
    session.commit()

    hiring_svc.run_autohire(admin, term_id)

    assignments = session.scalars(
        select(HiringAssignmentEntity)
        .where(HiringAssignmentEntity.user_id == student.id)
        .where(HiringAssignmentEntity.term_id == term_id)
        .where(HiringAssignmentEntity.status == HiringAssignmentStatus.DRAFT)
    ).all()

    assert len(assignments) == 1
    
    assert assignments[0].course_site_id == site_1.id


def test_run_autohire_stops_at_budget_limit(hiring_svc: HiringService, session: Session):
    """
    Test that budget limits are respected. If hiring a second student pushes coverage 
    beyond the limit (e.g., > 1.0), the system stops hiring for that course.
    """
    admin = user_data.root
    term_id = term_data.current_term.id
    
    session.execute(text("SELECT setval('academics__hiring__assignment_id_seq', 100, true)"))
    session.commit()

    site_id = office_hours_data.comp_110_site.id
    site_entity = session.get(CourseSiteEntity, site_id)
    
    for section in site_entity.sections:
        section.enrolled = 0
    site_entity.sections[0].enrolled = 60
    session.add(site_entity.sections[0])
    
    uta_level_id = hiring_data.uta_level.id 
    
    rev1 = ApplicationReviewEntity(
        application_id=hiring_data.application_two.id,
        course_site_id=site_entity.id,
        status=ApplicationReviewStatus.PREFERRED,
        preference=0,
        level_id=uta_level_id, 
        notes=""
    )
    rev2 = ApplicationReviewEntity(
        application_id=hiring_data.application_three.id,
        course_site_id=site_entity.id,
        status=ApplicationReviewStatus.PREFERRED,
        preference=1,
        level_id=uta_level_id,
        notes=""
    )
    session.add_all([rev1, rev2])
    session.commit()

    hiring_svc.run_autohire(admin, term_id)

    assignments = session.scalars(
        select(HiringAssignmentEntity)
        .where(HiringAssignmentEntity.course_site_id == site_entity.id)
        .where(HiringAssignmentEntity.status == HiringAssignmentStatus.DRAFT)
    ).all()

    assert len(assignments) == 1


def test_run_autohire_skips_if_level_missing(hiring_svc: HiringService, session: Session):
    """If a student is preferred by an instructor, but not given a preferred hiring level 
    that student does not have a hiring assignment created"""
    admin = user_data.root
    term_id = term_data.current_term.id
    site_id = office_hours_data.comp_110_site.id
    site_entity = session.get(CourseSiteEntity, site_id)
    
    rev = ApplicationReviewEntity(
        application_id=hiring_data.application_four.id,
        course_site_id=site_entity.id,
        status=ApplicationReviewStatus.PREFERRED,
        preference=0,
        level_id=None,
        notes="Forgot Level"
    )
    session.add(rev)
    session.commit()

    hiring_svc.run_autohire(admin, term_id)

    assignment = session.scalars(
        select(HiringAssignmentEntity)
        .where(HiringAssignmentEntity.user_id == user_data.uta.id)
    ).first()
    
    assert assignment is None

def test_run_autohire_permissions(hiring_svc: HiringService):
    """Ensures that instructors can not run the autohire feature"""
    with pytest.raises(UserPermissionException):
        hiring_svc.run_autohire(user_data.instructor, term_data.current_term.id)