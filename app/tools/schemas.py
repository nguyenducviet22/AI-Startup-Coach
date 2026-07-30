from typing import Annotated, Literal

from app.domain.stages import StageName
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True)]

class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GenerateLeanCanvasArgs(ToolArguments):
    problem: NonEmptyString
    solution: NonEmptyString
    unique_value_proposition: NonEmptyString
    customer_segments: NonEmptyString
    unfair_advantage: OptionalText = ""
    key_metrics: OptionalText = ""
    channels: OptionalText = ""
    cost_structure: OptionalText = ""
    revenue_streams: OptionalText = ""


class GenerateBmcArgs(ToolArguments):
    customer_segments: NonEmptyString
    value_propositions: NonEmptyString
    key_partners: OptionalText = ""
    key_activities: OptionalText = ""
    key_resources: OptionalText = ""
    customer_relationships: OptionalText = ""
    channels: OptionalText = ""
    cost_structure: OptionalText = ""
    revenue_streams: OptionalText = ""


class GenerateSwotArgs(ToolArguments):
    strengths: list[NonEmptyString] = Field(min_length=1)
    weaknesses: list[NonEmptyString] = Field(min_length=1)
    opportunities: list[NonEmptyString] = Field(min_length=1)
    threats: list[NonEmptyString] = Field(min_length=1)


FeaturePriority = Literal["must-have", "should-have", "nice-to-have"]
FeatureEffort = Literal["low", "medium", "high"]


class ProductFeature(ToolArguments):
    name: NonEmptyString
    priority: FeaturePriority
    effort: FeatureEffort


class ProductMilestone(ToolArguments):
    milestone: NonEmptyString
    target_date: NonEmptyString


class GenerateProductPlanArgs(ToolArguments):
    mvp_scope: NonEmptyString
    features: list[ProductFeature] = Field(min_length=1)
    timeline: list[ProductMilestone] = Field(default_factory=list)


class GenerateMarketingStrategyArgs(ToolArguments):
    target_audience: NonEmptyString
    channels: list[NonEmptyString] = Field(min_length=1)
    key_messages: OptionalText = ""
    budget_estimate: OptionalText = ""


class FundingPitchSlide(ToolArguments):
    slide_title: NonEmptyString
    content: NonEmptyString


class GenerateFundingGuideArgs(ToolArguments):
    pitch_outline: list[FundingPitchSlide] = Field(min_length=1)
    valuation_notes: OptionalText = ""
    funding_stage_recommendation: OptionalText = ""


class CheckStageReadinessArgs(ToolArguments):
    current_stage: StageName
    ready: bool
    missing_fields: list[NonEmptyString] = Field(default_factory=list)
