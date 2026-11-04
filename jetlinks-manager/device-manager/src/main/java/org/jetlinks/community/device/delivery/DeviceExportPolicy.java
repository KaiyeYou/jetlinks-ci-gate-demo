/*
 * Copyright 2025 JetLinks https://www.jetlinks.cn
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.jetlinks.community.device.delivery;

/**
 * Quality contract for exporting device instances.
 *
 * <p>An export request may contain at most {@value #MAX_EXPORT_ROWS} rows,
 * including the boundary value itself. Larger exports should be implemented as
 * asynchronous jobs instead of holding a request and database cursor open.</p>
 */
public final class DeviceExportPolicy {

    public static final int MAX_EXPORT_ROWS = 5_000;

    private DeviceExportPolicy() {
    }

    public static int requireAllowed(int requestedRows) {
        if (!isWithinLimit(requestedRows)) {
            throw new IllegalArgumentException(
                "device export rows must be between 1 and " + MAX_EXPORT_ROWS
            );
        }
        return requestedRows;
    }

    public static boolean isWithinLimit(int requestedRows) {
        return requestedRows > 0 && requestedRows <= MAX_EXPORT_ROWS;
    }
}
