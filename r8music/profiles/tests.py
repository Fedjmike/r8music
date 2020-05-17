import requests_mock

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

class SettingsTest(TestCase):
    def test_validation(self):
        def test_form_response(response, expected_errors):
            for form_name in ["user_form", "settings_form", "profile_form"]:
                form = response.context_data[form_name]
                
                expected_error_fields = expected_errors.get(form_name, [])
                
                self.assertEqual(set(form.errors.keys()), set(expected_error_fields), form_name)
                
                if not expected_error_fields:
                    self.assertTrue(form.is_valid())
                    
        def test_form_submission(extra_fields, *error_args, extra_request_mock=lambda mock: None):
            avatar_url = "https://i.imgur.com/image.jpg"
            
            #These values will be accepted without errors
            fields = {"email": "x@y.com", "timezone": "Europe/London", "avatar_url": avatar_url}
            
            fields.update(extra_fields)
            
            with requests_mock.mock() as mock:
                mock.head(avatar_url, headers={"content-length": "0"})
                extra_request_mock(mock)
                
                response = self.client.post(reverse("settings"), fields)
                test_form_response(response, *error_args)
            
        user = User.objects.create_user("user", "email@email.com", "password")
        self.client.force_login(user)
        
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 200)
        
        #No fields changed, no errors
        test_form_submission({}, {})
        
        test_form_submission({"email": "invalid email"}, {"user_form": ["email"]})
        test_form_submission({"timezone": "invalid timezone"}, {"settings_form": ["timezone"]})
        test_form_submission({"avatar_url": "invalid URL"}, {"profile_form": ["avatar_url"]})
        
        test_form_submission({"avatar_url": "http://not-whitelisted.com/image.jpg"}, {"profile_form": ["avatar_url"]})
        test_form_submission({"avatar_url": "http://i.imgur.com/no-extension"}, {"profile_form": ["avatar_url"]})
        
        mock_404_url = "http://i.imgur.com/not-here.jpg"
        test_form_submission(
            {"avatar_url": mock_404_url}, {"profile_form": ["avatar_url"]},
            extra_request_mock=lambda mock: mock.head(mock_404_url, status_code=404)
        )
