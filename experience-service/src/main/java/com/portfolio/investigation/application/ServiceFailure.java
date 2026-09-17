package com.portfolio.investigation.application;

public final class ServiceFailure extends RuntimeException {
    public enum Kind { NOT_FOUND, UNAVAILABLE, TIMEOUT, BAD_RESPONSE }
    private final Kind kind;
    public ServiceFailure(Kind kind) {
        super(kind.name()); // Never preserve a downstream body, URL, or exception message.
        this.kind = kind;
    }
    public Kind kind() { return kind; }
}
