import boto3
import json

def run():
    with open('data/sqs_queues.json') as f:
        sqs_queues = json.load(f)

    session = boto3.Session(profile_name='aws2025')
    sqs = session.client('sqs', region_name='eu-south-2')

    for queue in sqs_queues:
        queue_name = queue['Attributes']['QueueArn'].split(':')[-1]
        attributes = queue['Attributes'].copy()
        # Remove read-only attributes that cannot be set on creation
        for key in ['QueueArn', 'CreatedTimestamp', 'LastModifiedTimestamp', 'QueueUrl']:
            attributes.pop(key, None)

        print(f"Creating SQS queue: {queue_name}")
        try:
            response = sqs.create_queue(
                QueueName=queue_name,
                Attributes=attributes
            )
            new_queue_url = response['QueueUrl']

            # Add tags if present
            if queue.get('Tags'):
                sqs.tag_queue(
                    QueueUrl=new_queue_url,
                    Tags=queue['Tags']
                )

        except Exception as e:
            print(f"Error creating queue {queue_name}: {e}")

run()
