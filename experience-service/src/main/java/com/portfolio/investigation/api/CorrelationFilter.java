package com.portfolio.investigation.api;

import java.io.IOException;
import java.util.UUID;
import java.util.regex.Pattern;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class CorrelationFilter extends OncePerRequestFilter {
    public static final String HEADER = "X-Correlation-Id";
    private static final Pattern UUID_PATTERN = Pattern.compile("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}");
    private static final Logger log = LoggerFactory.getLogger(CorrelationFilter.class);
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String header = request.getHeader(HEADER);
        String id = header != null && UUID_PATTERN.matcher(header).matches()
                ? UUID.fromString(header).toString() : UUID.randomUUID().toString();
        request.setAttribute(HEADER, id);
        response.setHeader(HEADER, id);
        long start = System.nanoTime();
        String previous = MDC.get("correlationId");
        MDC.put("correlationId", id);
        try { chain.doFilter(request, response); }
        finally {
            // Do not log URLs, request bodies, questions or downstream error bodies.
            log.atInfo().addKeyValue("event", "http_request").addKeyValue("status", response.getStatus())
                .addKeyValue("durationMs", (System.nanoTime()-start)/1_000_000).log("HTTP request finished");
            if (previous == null) MDC.remove("correlationId"); else MDC.put("correlationId", previous);
        }
    }
}
