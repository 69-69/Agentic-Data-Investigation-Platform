package com.portfolio.investigation;

import org.junit.jupiter.api.Test;
import com.portfolio.investigation.application.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class InvestigationServiceTest {
    private final AgentGateway gateway = mock(AgentGateway.class);
    private final InvestigationService service = new InvestigationService(gateway);
    @Test void createUsesPortAndPreservesCorrelation() {
        var result = Fixtures.result();
        when(gateway.create(Fixtures.QUESTION, "trace")).thenReturn(result);
        assertThat(service.create(Fixtures.QUESTION, "trace")).isSameAs(result);
        verify(gateway).create(Fixtures.QUESTION, "trace");
    }
    @Test void lookupUsesAgentOwnedState() {
        when(gateway.get(Fixtures.ID, "trace")).thenReturn(Fixtures.result());
        assertThat(service.get(Fixtures.ID, "trace").id()).isEqualTo(Fixtures.ID);
        verify(gateway).get(Fixtures.ID, "trace");
    }
    @Test void failureDoesNotCreateFakeResult() {
        var failure = new ServiceFailure(ServiceFailure.Kind.UNAVAILABLE);
        when(gateway.create(anyString(), anyString())).thenThrow(failure);
        assertThatThrownBy(() -> service.create(Fixtures.QUESTION, "trace")).isSameAs(failure);
        verifyNoMoreInteractionsAfterFailure();
    }
    private void verifyNoMoreInteractionsAfterFailure() {
        verify(gateway).create(Fixtures.QUESTION, "trace");
        verifyNoMoreInteractions(gateway);
    }
    @Test void lookupNotFoundIsPreserved() {
        when(gateway.get(Fixtures.ID, "trace")).thenThrow(new ServiceFailure(ServiceFailure.Kind.NOT_FOUND));
        assertThatThrownBy(() -> service.get(Fixtures.ID, "trace"))
            .isInstanceOf(ServiceFailure.class).hasMessage("NOT_FOUND");
    }
}
