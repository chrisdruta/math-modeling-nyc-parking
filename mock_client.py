class MockClient:
    def __init__(self):
        self.directionCount = 0
        self.distanceCount = 0
    
    def directions(self, origin, destination):
        self.directionCount += 1
        
        return [
            {
                'legs': [
                    {
                        'duration': {
                            'value': 900
                        },
                        'steps': [
                            {
                                'duration': {
                                    'value': 90
                                },
                                'end_location': {
                                    'lat': 40.760862,
                                    'lng': -73.982418,
                                }
                            }
                        ] * 10
                    }
                ]
            }
        ]

    def distance_matrix(self, origins, destinations):
        self.distanceCount += 1
        return {
            'rows': [
                {
                    'elements': [
                        {
                            'duration':{
                                'value': 900
                            }
                        }
                    ]
                }
            ] * len(origins)
        }
        