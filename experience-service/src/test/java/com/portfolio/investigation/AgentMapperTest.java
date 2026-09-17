package com.portfolio.investigation;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.AfterAll;
import jakarta.validation.Validation;
import com.portfolio.investigation.adapter.agent.*;
import com.portfolio.investigation.application.ServiceFailure;
import tools.jackson.databind.json.JsonMapper;
import static org.assertj.core.api.Assertions.*;

class AgentMapperTest {
    private static final jakarta.validation.ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
    private final AgentMapper mapper = new AgentMapper(factory.getValidator());
    private final JsonMapper json = JsonMapper.builder().build();
    private AgentPayload payload(String text) { return json.readValue(text, AgentPayload.class); }
    @AfterAll static void close() { factory.close(); }
    @Test void mapsEvidenceWithoutLeakingInternalTypes() {
        var result = mapper.map(payload(Fixtures.json()));
        assertThat(result.evidence().getFirst().sqlQueryId()).isEqualTo("s1");
        assertThat(result.findings().getFirst().evidenceIds()).containsExactly("e1");
    }
    @Test void rejectsUnknownEvidenceReferences() {
        assertThatThrownBy(() -> mapper.map(payload(Fixtures.json().replace("[\"e1\"]", "[\"unknown\"]"))))
            .isInstanceOf(ServiceFailure.class);
    }
    @Test void rejectsMissingFields() {
        assertThatThrownBy(() -> mapper.map(payload("{}"))).isInstanceOf(ServiceFailure.class);
    }
    @Test void rejectsUnknownStatus() {
        assertThatThrownBy(() -> mapper.map(payload(Fixtures.json().replace("\"status\":\"completed\",", "\"status\":\"surprise\","))))
            .isInstanceOf(ServiceFailure.class);
    }
    @Test void rejectsTerminalWithoutCompletionTime() {
        assertThatThrownBy(() -> mapper.map(payload(Fixtures.json().replace("\"2026-06-22T01:00:02Z\"", "null"))))
            .isInstanceOf(ServiceFailure.class);
    }
    @Test void sanitizesFailedInvestigationError() {
        var result = mapper.map(payload(Fixtures.json().replaceFirst("completed", "failed")));
        assertThat(result.error().code()).isEqualTo("INVESTIGATION_FAILED");
    }
    @Test void mapsPromptSixFieldsToPublicResult() {
        var text = Fixtures.json().replace("\"summary\":", "\"probableRootCause\":\"Possible ingestion failure\",\"confidence\":0.65,\"summary\":")
            .replace("\"description\":\"Volume declined\"", "\"title\":\"Volume comparison\",\"confidence\":0.9,\"description\":\"Volume declined\"");
        var result = com.portfolio.investigation.api.ApiDtos.result(mapper.map(payload(text)));
        assertThat(result.confidence()).isEqualTo(0.65);
        assertThat(result.probableRootCause()).isEqualTo("Possible ingestion failure");
        assertThat(result.findings().getFirst().title()).isEqualTo("Volume comparison");
        assertThat(result.findings().getFirst().confidence()).isEqualTo(0.9);
        assertThat(result.evidence().getFirst().type()).isEqualTo("sql_result");
        assertThat(result.evidence().getFirst().query()).isEqualTo(result.sqlQueries().getFirst().sql());
        assertThat(result.evidence().getFirst().rowCount()).isEqualTo(1);
    }
    @Test void rejectsOutOfRangeConfidence() {
        var text = Fixtures.json().replace("\"summary\":", "\"confidence\":1.5,\"summary\":");
        assertThatThrownBy(() -> mapper.map(payload(text))).isInstanceOf(ServiceFailure.class);
    }
}
