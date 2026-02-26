Feature: User File Browser
  As an authenticated user
  I want to browse, upload, and download files
  So that I can manage my shared content

  Background:
    Given I am logged in as a regular user

  Scenario: View the file browser
    When I navigate to "/files"
    Then I should see the file browser

  Scenario: Upload a file
    Given I am on the file browser page
    When I upload a file named "test-upload.txt"
    Then I should see "test-upload.txt" in the file list

  Scenario: Download a file
    Given I am on the file browser page
    And a file named "test-upload.txt" exists
    When I download the file "test-upload.txt"
    Then the download should start
