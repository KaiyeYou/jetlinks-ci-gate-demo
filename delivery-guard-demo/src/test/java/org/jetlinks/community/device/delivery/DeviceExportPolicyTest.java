package org.jetlinks.community.device.delivery;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class DeviceExportPolicyTest {

    @Test
    void acceptsARegularExport() {
        assertEquals(4_999, DeviceExportPolicy.requireAllowed(4_999));
    }

    @Test
    void rejectsAnExportAboveTheLimit() {
        assertThrows(
            IllegalArgumentException.class,
            () -> DeviceExportPolicy.requireAllowed(5_001)
        );
    }

    @Test
    void rejectsNonPositiveExportSize() {
        assertThrows(
            IllegalArgumentException.class,
            () -> DeviceExportPolicy.requireAllowed(0)
        );
    }
}
