package com.portfolio.investigation;

import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;
import com.portfolio.investigation.api.ApiDtos;
import static org.assertj.core.api.Assertions.*;

class OpenApiContractTest {
    @Test @SuppressWarnings("unchecked") void documentedPropertiesMatchFrontendRecords() throws Exception {
        try (var stream = getClass().getResourceAsStream("/static/openapi.json")) {
            var document = JsonMapper.builder().build().readValue(stream, Map.class);
            var schemas = (Map<String, Map<String, Object>>) ((Map<?, ?>)document.get("components")).get("schemas");
            for (var type : new Class<?>[]{ApiDtos.CreateRequest.class, ApiDtos.Created.class, ApiDtos.Result.class,
                    ApiDtos.Finding.class, ApiDtos.Evidence.class, ApiDtos.SqlQuery.class, ApiDtos.ToolExecution.class,
                    ApiDtos.ErrorDetail.class, ApiDtos.ErrorResponse.class}) {
                var properties = (Map<String, Object>) schemas.get(type.getSimpleName()).get("properties");
                assertThat(properties.keySet()).isEqualTo(Arrays.stream(type.getRecordComponents())
                    .map(java.lang.reflect.RecordComponent::getName).collect(Collectors.toSet()));
            }
        }
    }
}
