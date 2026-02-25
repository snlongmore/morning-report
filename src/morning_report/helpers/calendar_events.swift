#!/usr/bin/env swift

// Fetches calendar events using EventKit (native macOS framework).
// Much faster than AppleScript which times out on large calendars.
//
// Usage: swift calendar_events.swift <lookahead_days> [calendar_name1,calendar_name2,...]
// Output: JSON array of events to stdout

import EventKit
import Foundation

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)

// Parse arguments
let args = CommandLine.arguments
let lookaheadDays = args.count > 1 ? Int(args[1]) ?? 3 : 3
let calendarFilter: Set<String>? = args.count > 2
    ? Set(args[2].split(separator: ",").map { String($0) })
    : nil

// Request calendar access
var accessGranted = false

if #available(macOS 14.0, *) {
    store.requestFullAccessToEvents { granted, error in
        accessGranted = granted
        semaphore.signal()
    }
} else {
    store.requestAccess(to: .event) { granted, error in
        accessGranted = granted
        semaphore.signal()
    }
}

semaphore.wait()

guard accessGranted else {
    let errorObj: [String: Any] = ["error": "Calendar access denied. Grant access in System Settings > Privacy & Security > Calendars."]
    if let data = try? JSONSerialization.data(withJSONObject: errorObj),
       let str = String(data: data, encoding: .utf8) {
        print(str)
    }
    exit(1)
}

// Build date range
let calendar = Calendar.current
let startOfToday = calendar.startOfDay(for: Date())
guard let endDate = calendar.date(byAdding: .day, value: lookaheadDays, to: startOfToday) else {
    print("[]")
    exit(0)
}

// Get matching calendars
var calendars = store.calendars(for: .event)
if let filter = calendarFilter {
    calendars = calendars.filter { filter.contains($0.title) }
}

// Query events
let predicate = store.predicateForEvents(withStart: startOfToday, end: endDate, calendars: calendars)
let events = store.events(matching: predicate)

// Convert to JSON
let dateFormatter = DateFormatter()
dateFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"

var jsonEvents: [[String: Any]] = []
for event in events {
    var dict: [String: Any] = [
        "calendar": event.calendar.title,
        "title": event.title ?? "(no title)",
        "start": dateFormatter.string(from: event.startDate),
        "end": dateFormatter.string(from: event.endDate),
        "all_day": event.isAllDay,
    ]
    if let location = event.location, !location.isEmpty {
        dict["location"] = location
    } else {
        dict["location"] = ""
    }
    if let notes = event.notes, !notes.isEmpty {
        // Truncate long notes
        dict["notes"] = String(notes.prefix(500))
    } else {
        dict["notes"] = ""
    }
    jsonEvents.append(dict)
}

// Sort by start date (already sorted by EventKit, but ensure)
if let data = try? JSONSerialization.data(withJSONObject: jsonEvents, options: [.prettyPrinted, .sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
} else {
    print("[]")
}
