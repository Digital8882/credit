from crewai import Task

# Define the tasks as per the required template
icp_task = Task(
    description=f"""Your task is to create a detailed ideal customer profile that will guide marketing and product development strategies for a business selling the product ."
            "To generate the ICP, consider the following:"
            "- Analyze the provided customer feedback, market research, and industry reports to identify patterns and insights about the target customer"
            "- Determine the demographic, geographic, and psychographic characteristics of the ideal customer"
            "- Identify the customer's pain points, needs, and challenges related to the product or service"
            "- Describe the customer's goals, desires, and aspirations that the product or service can help fulfill"
            "- Summarize the customer's preferred communication channels and media consumption habits"
            "- List the customer's most common objections and hesitations when considering a purchase of the product or service"
            "- Explore the factors that influence the customer's decision-making process when choosing a product or service in the relevant category"
            "- Create a memorable and relatable name for the ICP that reflects the target customer's characteristics or role (e.g., "Marketing Manager Molly," "Fitness Enthusiast Frank")"
            "If the majority of the target customers are men, use a male example in the profile. If the majority are women, use a female example."
            "The ICP should be written in a professional, analytical tone, with clarity and accessibility necessary for understanding by team members across different functions."
            "Remember to regularly review and update the ICP based on new customer data, market trends, and product changes.""",
    expected_output=f""" Create an ideal customer profile document of approximately 500 words , including:"
            "a story-like format that is easy to understand and remember. For example:
            "Meet [Name], a [age]-year-old [gender] who works as a [occupation] in [location]. [Name] values [values] and enjoys [interests/hobbies] in their free time. As a [personality trait] person, [Name] struggles with [pain point/challenge] when it comes to [product/service category]. They aspire to [goal/desire] and believe that the right [product/service] can help them achieve this. [Name] prefers to communicate via [preferred channels] and often consumes media through [media habits]. When considering a purchase, [Name] typically [decision-making process description] and their main concerns are [objections/hesitations]."
            "- A detailed description of the target customer, including:"
            "- Demographic characteristics (e.g., age, gender, income, education, occupation)"
            "- Geographic characteristics (e.g., location, urban/rural, climate)"
            "- Psychographic characteristics (e.g., personality, values, interests, lifestyle)"
            "- A list of the customer's pain points, needs, challenges and jobs to be done some related to the product or service and some outside the scope of our offering but are still important to the customer 4-6 of each."
            "- A description of the customer's goals, desires, and aspirations that the product or service can help fulfill"
            "- A summary of the customer's preferred communication channels (e.g., email, social media, phone) and media consumption habits (e.g., blogs, podcasts, magazines)"
            "- A list of the customer's most common objections and hesitations when considering a purchase of the product or service"
            "- A description of the customer's typical decision-making process, including the steps they take, the information they seek, and the criteria they use to evaluate options"
            "Format the document as a concise, structured report with headings, subheadings, and bullet points for easy reference and sharing among team members."
            "Conclude the ICP with of how the key characteristics can inform marketing and product development strategies."
            "Emphasize the importance of continuously refining the ICP based on new customer data, market trends, and product changes, and suggest a timeline for periodic reviews (e.g., quarterly or bi-annually)."
            "If insufficient information is provided about the target customer or product/service, make reasonable assumptions or provide generic examples, while clearly stating the limitations.""",
    )
