import { GeoCompanionApiClient } from "./generated";

const client = new GeoCompanionApiClient();

void client.get_lesson_api_v1_lessons__lesson_id__get("bollards");
void client.submit_feedback_api_v1_feedback_post({ attempt_id: "attempt-1", round_id: "r1", rating: 3 });
void client.submit_practice_answer_api_v1_practice_rounds__round_id__answers_post("r1", {
  country_code: "SK",
  coordinate: { latitude: 48.1486, longitude: 17.1077 },
});

// @ts-expect-error request bodies must not be optional
void client.submit_feedback_api_v1_feedback_post();
// @ts-expect-error the generated path parameter must be supplied as a string
void client.get_lesson_api_v1_lessons__lesson_id__get();
