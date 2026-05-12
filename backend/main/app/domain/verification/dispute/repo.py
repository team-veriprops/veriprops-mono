from kink import inject
from main.app.domain.verification.dispute.models import (
    Dispute, DisputeResolution,
    CreateDisputeDto, UpdateDisputeDto, QueryDisputeDto, SearchDisputeDto,
    CreateDisputeResolutionDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class DisputeRepo(GenericRepo[
    Dispute, CreateDisputeDto, UpdateDisputeDto, QueryDisputeDto, SearchDisputeDto,
]):
    model = Dispute


@inject
class DisputeResolutionRepo(GenericRepo[
    DisputeResolution, CreateDisputeResolutionDto, CreateDisputeResolutionDto,
    QueryDisputeDto, SearchDisputeDto,
]):
    model = DisputeResolution
